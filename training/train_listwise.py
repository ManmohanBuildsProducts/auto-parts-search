"""CADeT listwise distillation training script — runs on HF Jobs A100.

Loads:
  - ManmohanBuildsProducts/auto-parts-listwise-v1 → listwise KL loss (new signal)
  - ManmohanBuildsProducts/auto-parts-search-pairs → golden-v2 InfoNCE (preserves domain adaptation)
Base:  ManmohanBuildsProducts/auto-parts-search-v3  (v3 not BGE-m3 — keeps +35% domain adaptation)
Loss:  Interleaved: listwise batches use ListwiseKLLoss (KL+InfoNCE λ=0.6/0.4);
       golden-v2 batches use InfoNCE-only (in-batch NCE, diagonal targets).
Out:   ManmohanBuildsProducts/auto-parts-search-v4-cadet (private)

Training ratio: 2 listwise batches : 1 golden-v2 batch (golden-v2 = 26,760 pairs, listwise ~20K).

Usage on HF Jobs:
    Set env vars: HF_TOKEN
    python3 training/train_listwise.py

Usage locally (smoke test, tiny subset):
    HF_TOKEN=... python3 training/train_listwise.py --smoke-test
"""
from __future__ import annotations

import argparse
import json
import os
import torch
import torch.nn.functional as F
from itertools import cycle
from pathlib import Path

from datasets import load_dataset
from sentence_transformers import SentenceTransformer
from torch.utils.data import DataLoader, Dataset as TorchDataset

from training.listwise_loss import ListwiseKLLoss

HF_TOKEN = os.environ.get("HF_TOKEN", "")
LISTWISE_DATASET = "ManmohanBuildsProducts/auto-parts-listwise-v1"
GOLDEN_DATASET = "ManmohanBuildsProducts/auto-parts-search-pairs"
BASE_MODEL = "ManmohanBuildsProducts/auto-parts-search-v3"
OUTPUT_REPO = "ManmohanBuildsProducts/auto-parts-search-v4-cadet"
EPOCHS = 3
BATCH_SIZE = 16
LR = 2e-5
MAX_SEQ_LEN = 128
GOLDEN_INTERLEAVE_RATIO = 2  # 1 golden-v2 batch per N listwise batches


class ListwiseDataset(TorchDataset):
    def __init__(self, hf_dataset):
        self.records = list(hf_dataset)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx):
        rec = self.records[idx]
        query = rec["query"]
        cand_titles = json.loads(rec["candidate_doc_titles"])
        teacher_scores = json.loads(rec["teacher_scores"])
        gold_title = rec["gold_doc_title"]

        # Gold doc always at index 0 for InfoNCE component
        if gold_title in cand_titles:
            gold_idx = cand_titles.index(gold_title)
            cand_titles.insert(0, cand_titles.pop(gold_idx))
            teacher_scores.insert(0, teacher_scores.pop(gold_idx))
        else:
            cand_titles.insert(0, gold_title)
            teacher_scores.insert(0, 1.0)

        return {
            "query": query,
            "candidates": cand_titles[:20],
            "teacher_scores": torch.tensor(teacher_scores[:20], dtype=torch.float),
        }


class GoldenV2Dataset(TorchDataset):
    """Golden-v2 pair dataset for InfoNCE-only training.

    Columns: text_a, text_b, label (1.0 = same-intent, 0.5 = co-occurrence).
    Only label==1.0 pairs are safe as InfoNCE positives.
    In-batch negatives are formed by grouping BATCH_SIZE pairs together.
    """
    def __init__(self, hf_dataset):
        self.records = [
            {"query": r["text_a"], "positive": r["text_b"]}
            for r in hf_dataset
            if r.get("text_a") and r.get("text_b") and r.get("label") == 1.0
        ]

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx):
        return self.records[idx]


def encode(model: SentenceTransformer, texts: list[str], device: str) -> torch.Tensor:
    """Encode texts with gradient support for training."""
    features = model.tokenize(texts)
    features = {k: v.to(device) for k, v in features.items()}
    out = model(features)
    emb = out["sentence_embedding"]
    return torch.nn.functional.normalize(emb, p=2, dim=-1)


def train(smoke_test: bool = False) -> None:
    print(f"base model: {BASE_MODEL}")
    print(f"loading listwise dataset {LISTWISE_DATASET}...")
    listwise_ds = load_dataset(LISTWISE_DATASET, split="train", token=HF_TOKEN)
    print(f"loading golden-v2 dataset {GOLDEN_DATASET}...")
    golden_ds = load_dataset(GOLDEN_DATASET, split="train", token=HF_TOKEN)

    if smoke_test:
        listwise_ds = listwise_ds.select(range(min(200, len(listwise_ds))))
        golden_ds = golden_ds.select(range(min(100, len(golden_ds))))

    print(f"  listwise: {len(listwise_ds)} | golden-v2: {len(golden_ds)}")

    model = SentenceTransformer(BASE_MODEL, trust_remote_code=True, token=HF_TOKEN)
    model.max_seq_length = MAX_SEQ_LEN
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    print(f"using {device.upper()}")

    if device == "cuda":
        model[0].auto_model.gradient_checkpointing_enable()

    criterion = ListwiseKLLoss(lambda_listwise=0.6, lambda_infonce=0.4)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR)

    listwise_steps_per_epoch = len(listwise_ds) // BATCH_SIZE
    golden_steps_per_epoch = listwise_steps_per_epoch // GOLDEN_INTERLEAVE_RATIO
    n_steps = (listwise_steps_per_epoch + golden_steps_per_epoch) * EPOCHS
    scheduler = torch.optim.lr_scheduler.LinearLR(
        optimizer, start_factor=1.0, end_factor=0.0, total_iters=max(n_steps, 1)
    )

    best_loss = float("inf")
    ckpt_dir = Path("checkpoints/cadet")
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    for epoch in range(1 if smoke_test else EPOCHS):
        model.train()
        epoch_loss = 0.0
        n_batches = 0

        listwise_loader = DataLoader(
            ListwiseDataset(listwise_ds), batch_size=BATCH_SIZE, shuffle=True, collate_fn=lambda x: x
        )
        golden_loader = cycle(DataLoader(
            GoldenV2Dataset(golden_ds), batch_size=BATCH_SIZE, shuffle=True, collate_fn=lambda x: x
        ))

        for step, listwise_batch in enumerate(listwise_loader):
            # --- Listwise batch (KL + InfoNCE combined loss) ---
            queries = [item["query"] for item in listwise_batch]
            all_candidates = [item["candidates"] for item in listwise_batch]
            all_teacher = torch.stack([item["teacher_scores"] for item in listwise_batch]).to(device)

            q_emb = encode(model, queries, device)
            flat_cands = [c for cands in all_candidates for c in cands]
            flat_emb = encode(model, flat_cands, device)
            k = len(all_candidates[0])
            doc_embs = flat_emb.view(len(listwise_batch), k, -1)

            loss = criterion(q_emb, doc_embs, all_teacher)
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            epoch_loss += loss.item()
            n_batches += 1

            # --- Golden-v2 interleave batch (in-batch NCE, diagonal targets) ---
            if step % GOLDEN_INTERLEAVE_RATIO == 0:
                gold_batch = next(golden_loader)
                g_queries = [item["query"] for item in gold_batch]
                g_positives = [item["positive"] for item in gold_batch]

                g_q_emb = encode(model, g_queries, device)    # [B, D]
                g_p_emb = encode(model, g_positives, device)  # [B, D]
                # [B, B] score matrix — gold for query i is at column i
                scores = torch.mm(g_q_emb, g_p_emb.t()) / 0.05
                targets = torch.arange(len(gold_batch), device=device)
                g_loss = F.cross_entropy(scores, targets)
                optimizer.zero_grad()
                g_loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                epoch_loss += g_loss.item()
                n_batches += 1

        avg_loss = epoch_loss / max(n_batches, 1)
        print(f"epoch {epoch+1}/{EPOCHS} — avg loss: {avg_loss:.4f}")

        if avg_loss < best_loss:
            best_loss = avg_loss
            model.save(str(ckpt_dir / "best"))
            print(f"  saved best checkpoint (loss={best_loss:.4f})")

    # Push best checkpoint to HF Hub
    if not smoke_test:
        best_model = SentenceTransformer(str(ckpt_dir / "best"), trust_remote_code=True)
        best_model.push_to_hub(OUTPUT_REPO, private=True, token=HF_TOKEN)
        print(f"pushed → https://huggingface.co/ManmohanBuildsProducts/auto-parts-search-v4-cadet")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    train(smoke_test=args.smoke_test)

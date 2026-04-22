"""CADeT combined listwise KL + InfoNCE loss.

Reference: Tamber et al. 2025 (arxiv:2505.19274) — λ₁=0.6 KL + λ₂=0.4 InfoNCE.

Usage in training:
    criterion = ListwiseKLLoss(lambda_listwise=0.6, lambda_infonce=0.4)
    loss = criterion(query_emb, doc_embs, teacher_scores)
    loss.backward()
"""
from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import Tensor


def compute_listwise_kl(
    query_emb: Tensor,        # [B, D]
    doc_embs: Tensor,         # [B, K, D]
    teacher_scores: Tensor,   # [B, K] — raw cross-encoder logits, will be softmax'd
    temperature: float = 1.0,
) -> Tensor:
    """KL(student_probs ‖ teacher_probs) averaged over batch."""
    student_logits = torch.bmm(doc_embs, query_emb.unsqueeze(-1)).squeeze(-1) / temperature  # [B, K]
    student_log_probs = F.log_softmax(student_logits, dim=-1)
    teacher_probs = F.softmax(teacher_scores / temperature, dim=-1)
    return F.kl_div(student_log_probs, teacher_probs, reduction="batchmean")


def compute_infonce(
    query_emb: Tensor,  # [B, D]
    doc_embs: Tensor,   # [B, K, D] — index 0 is always the gold positive
    temperature: float = 0.05,
) -> Tensor:
    """Standard InfoNCE: gold doc at index 0 vs all K candidates."""
    logits = torch.bmm(doc_embs, query_emb.unsqueeze(-1)).squeeze(-1) / temperature  # [B, K]
    targets = torch.zeros(logits.size(0), dtype=torch.long, device=logits.device)
    return F.cross_entropy(logits, targets)


class ListwiseKLLoss(torch.nn.Module):
    def __init__(self, lambda_listwise: float = 0.6, lambda_infonce: float = 0.4):
        super().__init__()
        self.lambda_listwise = lambda_listwise
        self.lambda_infonce = lambda_infonce

    def forward(
        self,
        query_emb: Tensor,       # [B, D]
        doc_embs: Tensor,        # [B, K, D]
        teacher_scores: Tensor,  # [B, K]
    ) -> Tensor:
        kl = compute_listwise_kl(query_emb, doc_embs, teacher_scores)
        nce = compute_infonce(query_emb, doc_embs)
        return self.lambda_listwise * kl + self.lambda_infonce * nce

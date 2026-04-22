"""Tests for the CADeT combined listwise + InfoNCE loss."""
import torch
import pytest
from training.listwise_loss import ListwiseKLLoss, compute_listwise_kl, compute_infonce


def _rand_emb(batch: int, k: int, dim: int = 64) -> tuple[torch.Tensor, torch.Tensor]:
    """Returns (query_emb, doc_embs) with unit-normalized rows."""
    q = torch.randn(batch, dim)
    q = q / q.norm(dim=-1, keepdim=True)
    d = torch.randn(batch, k, dim)
    d = d / d.norm(dim=-1, keepdim=True)
    return q, d


def test_compute_listwise_kl_output_shape():
    q, d = _rand_emb(4, 20)
    teacher_scores = torch.randn(4, 20)
    loss = compute_listwise_kl(q, d, teacher_scores, temperature=1.0)
    assert loss.shape == ()
    assert loss.item() >= 0.0


def test_compute_infonce_output_shape():
    q, d = _rand_emb(4, 20)
    loss = compute_infonce(q, d)
    assert loss.shape == ()
    assert loss.item() >= 0.0


def test_listwise_kl_loss_decreases_with_perfect_teacher():
    """Student that matches teacher exactly should have near-zero KL loss."""
    q, d = _rand_emb(2, 5, dim=16)
    student_scores = torch.bmm(d, q.unsqueeze(-1)).squeeze(-1)
    loss = compute_listwise_kl(q, d, teacher_scores=student_scores)
    assert loss.item() < 0.01


def test_combined_loss_uses_both_components():
    """Combined loss must be a weighted sum of KL and InfoNCE."""
    q, d = _rand_emb(4, 10)
    teacher_scores = torch.randn(4, 10)
    criterion = ListwiseKLLoss(lambda_listwise=0.6, lambda_infonce=0.4)
    loss = criterion(q, d, teacher_scores)
    kl = compute_listwise_kl(q, d, teacher_scores)
    nce = compute_infonce(q, d)
    expected = 0.6 * kl + 0.4 * nce
    assert abs(loss.item() - expected.item()) < 1e-5


def test_loss_differentiable():
    """Loss must produce gradients for backprop."""
    q = torch.randn(2, 8, requires_grad=True)
    d = torch.randn(2, 5, 8, requires_grad=True)
    teacher_scores = torch.randn(2, 5)
    criterion = ListwiseKLLoss()
    loss = criterion(q, d, teacher_scores)
    loss.backward()
    assert q.grad is not None
    assert d.grad is not None

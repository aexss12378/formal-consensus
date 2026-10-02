# Lean 命題確認

請逐題比對「原題」與「這個命題在說什麼」。一致的話，把 `model_statement.draft.json` 裡該題的 `statement_fidelity_status` 從 `unresolved` 改成 `confirmed`；不一致就修改 `lean_theorem_header`，或刪掉該題。只有 `confirmed` 的題目會進入證明。

「這個命題在說什麼」是另一次模型呼叫只看 Lean 命題寫出的說明，它沒有看過原題，但它本身也可能寫錯。可以把每一題整段貼給你慣用的 AI，請它檢查 Lean 命題是否與原題完全一致。

## midterm_q8a_derivative

**原題**

Find the derivative of the function F(t) = (1/(2t + 1))^4.

**Lean 命題**

```lean
theorem midterm_q8a_derivative (t : ℝ) :
    deriv (fun s => (1 / (2 * s + 1)) ^ 4) t = -8 / (2 * t + 1) ^ 5 :=
```

**這個命題在說什麼**

The statement asserts: for every real number t (t is the only variable, of type "real number"; the theorem has no hypotheses, so it is an unconditional "for all t" claim), the derivative of the function s ↦ (1/(2s+1))^4, evaluated at the point t, equals the real number -8/(2t+1)^5.

Two Lean/Mathlib conventions affect the literal meaning:

1. "deriv" is Mathlib's total derivative operation. For a function f from the reals to the reals and a point t, "deriv f t" is the usual one-variable derivative of f at t whenever f is differentiable there; if f is NOT differentiable at t, "deriv f t" is defined to be 0. So the left-hand side is a well-defined real number for every t, differentiable or not.

2. Division by zero equals zero in Lean: a/0 = 0. Consequently the function s ↦ (1/(2s+1))^4 is defined on all of the reals — at s = -1/2 it takes the value (1/0)^4 = 0 — and the right-hand side -8/(2t+1)^5 is also defined for every t; at t = -1/2 it equals -8/0 = 0.

Literal content, point by point:

- For t ≠ -1/2, this is exactly the standard calculus computation: (1/(2s+1))^4 = (2s+1)^(-4), whose derivative is -4·(2s+1)^(-5)·2 = -8/(2s+1)^5. So for every t other than -1/2, the statement says the derivative of (1/(2s+1))^4 at t is -8/(2t+1)^5, matching the usual quotient/chain-rule answer.

- At t = -1/2 the equality still holds, but only degenerately. The function (1/(2s+1))^4 is not differentiable at s = -1/2 (it blows up as s approaches -1/2, while its Lean value at that point is 0 by the 1/0 = 0 convention), so the left-hand side is 0 by the "deriv is 0 when not differentiable" convention; the right-hand side is -8/0^5 = 0 by the division-by-zero convention. Thus at t = -1/2 the statement asserts 0 = 0, not the usual derivative formula.

In short: the theorem claims that the derivative of (1/(2s+1))^4 at any real point t is -8/(2t+1)^5 — the familiar answer from the chain rule for all t ≠ -1/2, and a convention-driven 0 = 0 at t = -1/2.

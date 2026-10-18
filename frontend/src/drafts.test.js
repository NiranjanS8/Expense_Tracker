import assert from "node:assert/strict";
import { test } from "node:test";

import {
  budgetFormFromDraft,
  draftFormLabel,
  draftTargetSection,
  expenseFormFromDraft,
} from "./drafts.js";
import { initialExpense } from "./lib.js";

const categories = [
  { id: 5, name: "Food" },
  { id: 7, name: "Transport" },
];

test("an expense draft fills the expense form without a request", () => {
  const form = expenseFormFromDraft(
    {
      kind: "expense",
      fields: {
        amount: 12.5,
        expenseDate: "2026-10-17",
        description: "coffee",
        categoryHint: "coffee",
      },
    },
    categories,
  );

  assert.deepEqual(form, {
    ...initialExpense,
    amount: "12.5",
    expenseDate: "2026-10-17",
    categoryId: "5",
    description: "coffee",
  });
});

test("a recognised category name is carried onto the form", () => {
  const form = expenseFormFromDraft(
    {
      kind: "expense",
      fields: { amount: 40, description: "lunch", categoryHint: "Food" },
    },
    categories,
  );

  assert.equal(form.categoryId, "5");
});

test("an unknown category hint falls back to no selection", () => {
  const form = expenseFormFromDraft(
    { kind: "expense", fields: { amount: 40, description: "gift" } },
    undefined,
  );

  assert.equal(form.categoryId, "");
});

test("a budget draft fills the budget form", () => {
  const form = budgetFormFromDraft({
    kind: "budget",
    fields: { amount: 5000, budgetMonth: "2026-11" },
  });

  assert.equal(form.amount, "5000");
  assert.equal(form.budgetMonth, "2026-11");
});

test("a draft names where it will be reviewed", () => {
  assert.equal(draftTargetSection({ kind: "expense" }), "overview");
  assert.equal(draftTargetSection({ kind: "budget" }), "budgets");
  assert.equal(draftFormLabel({ kind: "expense" }), "expense form");
  assert.equal(draftFormLabel({ kind: "budget" }), "budget form");
});

// Maps an assistant draft onto the application's own forms.
//
// The assistant only proposes values: these helpers turn a proposal into form
// state so the user does not retype it, and the user still saves it through the
// normal screen. Nothing here performs a request, so a draft can never become a
// record on its own.

import { initialBudget, initialExpense } from "./lib.js";

function matchCategoryId(categories, hint) {
  const target = String(hint || "").trim().toLowerCase();
  if (!target) {
    return "";
  }

  const match = (categories || []).find(
    (category) => String(category.name || "").trim().toLowerCase() === target,
  );
  return match ? String(match.id) : "";
}

export function expenseFormFromDraft(draft, categories) {
  const fields = draft?.fields || {};
  const categoryId =
    matchCategoryId(categories, fields.categoryHint) ||
    (categories?.length ? String(categories[0].id) : "");

  return {
    ...initialExpense,
    amount: fields.amount === undefined ? "" : String(fields.amount),
    expenseDate: fields.expenseDate || initialExpense.expenseDate,
    categoryId,
    description: fields.description || "",
  };
}

export function budgetFormFromDraft(draft) {
  const fields = draft?.fields || {};

  return {
    ...initialBudget,
    amount: fields.amount === undefined ? "" : String(fields.amount),
    budgetMonth: fields.budgetMonth || initialBudget.budgetMonth,
  };
}

// Where the form that a draft fills in already lives.
export function draftTargetSection(draft) {
  return draft?.kind === "budget" ? "budgets" : "overview";
}

export function draftFormLabel(draft) {
  return draft?.kind === "budget" ? "budget form" : "expense form";
}

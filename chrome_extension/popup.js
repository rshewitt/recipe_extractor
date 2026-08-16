const extractButton = document.querySelector("#extract");
const resetButton = document.querySelector("#reset");
const copyButton = document.querySelector("#copy");
const idle = document.querySelector("#idle");
const statusNode = document.querySelector("#status");
const recipeNode = document.querySelector("#recipe");
let currentRecipe = null;

extractButton.addEventListener("click", async () => {
  setStatus("Reading recipe data from this tab…");
  extractButton.disabled = true;
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) throw new Error("No active tab is available.");

    const [execution] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractRecipeFromPage,
    });

    const result = execution?.result;
    if (!result?.ok) {
      throw new Error(result?.message || "No Recipe JSON-LD was found on this page.");
    }

    currentRecipe = result.recipe;
    renderRecipe(currentRecipe);
  } catch (error) {
    setStatus(friendlyError(error), true);
  } finally {
    extractButton.disabled = false;
  }
});

resetButton.addEventListener("click", () => {
  currentRecipe = null;
  recipeNode.hidden = true;
  idle.hidden = false;
  statusNode.hidden = true;
});

copyButton.addEventListener("click", async () => {
  if (!currentRecipe) return;
  const text = recipeAsText(currentRecipe);
  await navigator.clipboard.writeText(text);
  copyButton.textContent = "Copied ✓";
  setTimeout(() => { copyButton.textContent = "Copy recipe"; }, 1400);
});

function renderRecipe(recipe) {
  idle.hidden = true;
  statusNode.hidden = true;
  recipeNode.hidden = false;
  document.querySelector("#recipe-title").textContent = recipe.title || "Untitled recipe";

  const meta = document.querySelector("#meta");
  meta.replaceChildren();
  addMeta(meta, "Serves", recipe.servings);
  addMeta(meta, "Prep", recipe.prepTime);
  addMeta(meta, "Cook", recipe.cookTime);
  addMeta(meta, "Total", recipe.totalTime);

  const ingredients = document.querySelector("#ingredients");
  ingredients.replaceChildren();
  for (const ingredient of recipe.ingredients || []) {
    const li = document.createElement("li");
    li.textContent = ingredient;
    ingredients.append(li);
  }

  const instructions = document.querySelector("#instructions");
  instructions.replaceChildren();
  for (const instruction of recipe.instructions || []) {
    const li = document.createElement("li");
    li.textContent = instruction;
    instructions.append(li);
  }
}

function addMeta(container, label, value) {
  if (!value) return;
  const div = document.createElement("div");
  const dt = document.createElement("dt");
  const dd = document.createElement("dd");
  dt.textContent = label;
  dd.textContent = value;
  div.append(dt, dd);
  container.append(div);
}

function setStatus(message, isError = false) {
  statusNode.textContent = message;
  statusNode.classList.toggle("error", isError);
  statusNode.hidden = false;
}

function friendlyError(error) {
  const message = error instanceof Error ? error.message : String(error);
  if (/Cannot access contents|chrome:\/\/|edge:\/\/|webstore/i.test(message)) {
    return "Chrome does not allow extensions to read this type of page. Open a normal recipe webpage and try again.";
  }
  return message;
}

function recipeAsText(recipe) {
  const parts = [recipe.title || "Recipe", ""];
  if (recipe.servings) parts.push(`Servings: ${recipe.servings}`);
  if (recipe.prepTime) parts.push(`Prep: ${recipe.prepTime}`);
  if (recipe.cookTime) parts.push(`Cook: ${recipe.cookTime}`);
  if (recipe.totalTime) parts.push(`Total: ${recipe.totalTime}`);
  parts.push("", "Ingredients");
  for (const ingredient of recipe.ingredients || []) parts.push(`- ${ingredient}`);
  parts.push("", "Instructions");
  (recipe.instructions || []).forEach((step, index) => parts.push(`${index + 1}. ${step}`));
  if (recipe.sourceUrl) parts.push("", `Source: ${recipe.sourceUrl}`);
  return parts.join("\n");
}

function extractRecipeFromPage() {
  const scripts = [...document.querySelectorAll('script[type="application/ld+json"]')];

  const hasRecipeType = (value) => {
    const type = value?.["@type"];
    return type === "Recipe" || (Array.isArray(type) && type.includes("Recipe"));
  };

  const findRecipe = (value, seen = new Set()) => {
    if (!value || typeof value !== "object" || seen.has(value)) return null;
    seen.add(value);

    if (Array.isArray(value)) {
      for (const item of value) {
        const found = findRecipe(item, seen);
        if (found) return found;
      }
      return null;
    }

    if (hasRecipeType(value)) return value;

    if (value["@graph"]) {
      const found = findRecipe(value["@graph"], seen);
      if (found) return found;
    }

    for (const child of Object.values(value)) {
      if (child && typeof child === "object") {
        const found = findRecipe(child, seen);
        if (found) return found;
      }
    }
    return null;
  };

  const instructionText = (value) => {
    if (!value) return [];
    if (typeof value === "string") return [value.trim()].filter(Boolean);
    if (Array.isArray(value)) return value.flatMap(instructionText);
    if (typeof value !== "object") return [];

    const type = value["@type"];
    if (type === "HowToSection") {
      return instructionText(value.itemListElement);
    }
    if (typeof value.text === "string" && value.text.trim()) {
      return [value.text.trim()];
    }
    if (typeof value.name === "string" && value.name.trim()) {
      return [value.name.trim()];
    }
    return instructionText(value.itemListElement);
  };

  for (const script of scripts) {
    try {
      const parsed = JSON.parse(script.textContent || "null");
      const recipe = findRecipe(parsed);
      if (!recipe) continue;

      const ingredients = Array.isArray(recipe.recipeIngredient)
        ? recipe.recipeIngredient.map(String).map((x) => x.trim()).filter(Boolean)
        : [];
      const instructions = instructionText(recipe.recipeInstructions);

      if (!ingredients.length || !instructions.length) continue;

      return {
        ok: true,
        recipe: {
          title: String(recipe.name || document.title || "Recipe").trim(),
          servings: Array.isArray(recipe.recipeYield)
            ? recipe.recipeYield.join(", ")
            : recipe.recipeYield ? String(recipe.recipeYield) : null,
          prepTime: recipe.prepTime ? String(recipe.prepTime) : null,
          cookTime: recipe.cookTime ? String(recipe.cookTime) : null,
          totalTime: recipe.totalTime ? String(recipe.totalTime) : null,
          ingredients,
          instructions,
          sourceUrl: location.href,
        },
      };
    } catch {
      // Ignore malformed JSON-LD and continue checking the remaining blocks.
    }
  }

  return {
    ok: false,
    message: "No usable Recipe JSON-LD was found on this page.",
  };
}

const form = document.querySelector("#recipe-form");
const statusNode = document.querySelector("#status");
const recipeNode = document.querySelector("#recipe");
const button = form.querySelector("button");
const buttonLabel = document.querySelector("#button-label");

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  recipeNode.hidden = true;
  setLoading(true);
  setStatus("Food Processor is working on it…");

  try {
    const url = new FormData(form).get("url");
    const response = await fetch("/api/recipes", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const result = await readJson(response);
    if (!response.ok) throw new Error(result.message || result.error || "Request failed");

    if (result.status === "COMPLETE") {
      renderRecipe(result.recipe);
      return;
    }

    await pollRecipe(result.recipe_id);
  } catch (error) {
    setStatus(error instanceof Error ? friendlyError(error.message) : "Unable to extract that recipe.", true);
  } finally {
    setLoading(false);
  }
});

async function pollRecipe(recipeId) {
  for (let attempt = 0; attempt < 45; attempt += 1) {
    await sleep(Math.min(1200 + attempt * 150, 3000));
    const response = await fetch(`/api/recipes/${encodeURIComponent(recipeId)}`, {
      headers: { accept: "application/json" },
    });
    const result = await readJson(response);
    if (!response.ok) throw new Error(result.message || result.error || "Status request failed");
    if (result.status === "COMPLETE") {
      renderRecipe(result.recipe);
      return;
    }
    if (result.status === "ERROR") {
      throw new Error(result.message || "The recipe could not be extracted from this page.");
    }
  }
  throw new Error("Recipe extraction is taking longer than expected. Try again shortly.");
}

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

function renderRecipe(recipe) {
  document.querySelector("#title").textContent = recipe.title;
  const description = document.querySelector("#description");
  description.textContent = recipe.description || "";
  description.hidden = !recipe.description;

  document.querySelector("#method").textContent =
    recipe.extraction_method === "json_ld" ? "Structured recipe data" : "AI-assisted extraction";

  const source = document.querySelector("#source");
  source.href = recipe.source_url;

  const meta = document.querySelector("#meta");
  meta.replaceChildren();
  addMeta(meta, "Servings", recipe.servings);
  addMeta(meta, "Prep", formatMinutes(recipe.prep_time_minutes));
  addMeta(meta, "Cook", formatMinutes(recipe.cook_time_minutes));
  addMeta(meta, "Total", formatMinutes(recipe.total_time_minutes));

  const ingredients = document.querySelector("#ingredients");
  ingredients.replaceChildren();
  let ingredientSection = null;
  for (const ingredient of recipe.ingredients) {
    if (ingredient.group && ingredient.group !== ingredientSection) {
      ingredientSection = ingredient.group;
      const heading = document.createElement("li");
      heading.className = "group-heading";
      heading.textContent = ingredientSection;
      ingredients.append(heading);
    }
    const item = document.createElement("li");
    item.textContent = ingredient.text;
    ingredients.append(item);
  }

  const instructions = document.querySelector("#instructions");
  instructions.replaceChildren();
  let instructionSection = null;
  for (const instruction of recipe.instructions) {
    if (instruction.section && instruction.section !== instructionSection) {
      instructionSection = instruction.section;
      const heading = document.createElement("li");
      heading.className = "group-heading instruction-group";
      heading.textContent = instructionSection;
      instructions.append(heading);
    }
    const item = document.createElement("li");
    item.value = instruction.step;
    item.textContent = instruction.text;
    instructions.append(item);
  }

  recipeNode.hidden = false;
  setStatus("Recipe processed successfully ✓");
  recipeNode.scrollIntoView({ behavior: "smooth", block: "start" });
}

function addMeta(container, label, value) {
  if (!value) return;
  const wrapper = document.createElement("div");
  const dt = document.createElement("dt");
  const dd = document.createElement("dd");
  dt.textContent = label;
  dd.textContent = value;
  wrapper.append(dt, dd);
  container.append(wrapper);
}

function formatMinutes(minutes) {
  if (!Number.isInteger(minutes) || minutes < 0) return null;
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} hr ${rest} min` : `${hours} hr`;
}

function setStatus(message, isError = false) {
  statusNode.textContent = message;
  statusNode.classList.toggle("error", isError);
}

function setLoading(isLoading) {
  button.disabled = isLoading;
  buttonLabel.textContent = isLoading ? "Processing…" : "Extract Recipe";
}

function friendlyError(message) {
  if (/HTTP 403|forbidden/i.test(message)) {
    return "This website blocked automated access. Try another recipe URL or use the browser-extension flow.";
  }
  if (/HTTP 429|rate/i.test(message)) {
    return "That website is rate limiting requests. Try again later.";
  }
  return message;
}

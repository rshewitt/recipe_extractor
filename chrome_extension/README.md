# Food Processor Chrome Extension (local development)

This is a dependency-free Chrome Manifest V3 extension for testing the Food Processor browser-side recipe extraction flow.

## Load it locally

1. Unzip this folder somewhere permanent on your computer.
2. Open `chrome://extensions` in Chrome.
3. Enable **Developer mode** in the top-right corner.
4. Click **Load unpacked**.
5. Select the unzipped `food-processor-extension` folder (the folder containing `manifest.json`).
6. Pin **Food Processor** from Chrome's Extensions menu.

## Test it

1. Open a recipe page in a normal browser tab.
2. Click the Food Processor extension.
3. Click **Extract Recipe**.

The extension reads `Recipe` JSON-LD already present in the page's DOM and displays a clean ingredient/instruction view. It only receives temporary access to the active tab after the user invokes it.

## Current scope

This local version intentionally does **not** call the AWS/localhost Food Processor API yet. It proves the browser-side extraction path that avoids server-side 403/bot blocking. The next integration step is to add an `/api/recipes/import` endpoint and send the extracted recipe payload to it.

## Development

After changing a file, return to `chrome://extensions` and click the reload icon on the Food Processor card. Then refresh the recipe webpage before testing again.

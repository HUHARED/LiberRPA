// FileName: snippetTreeIcons.ts

const STR_DEFAULT_CATEGORY_ICON = "library";

const DICT_SPECIAL_CATEGORY_ICON: Readonly<Record<string, string>> = {
  // Favorite is created by Snippets Tree at runtime and does not belong to a Catalog.
  Favorite: "sparkle",
};

// Return the VS Code Product Icon ID used by one Snippet category.
// Catalogs can provide Product Icon IDs only. Image paths, custom SVG files, and remote resources are intentionally unsupported so icons remain portable  and automatically follow the active VS Code Product Icon Theme.
// Choose an identifier from the second table under "Icon Listing": https://code.visualstudio.com/api/references/icons-in-labels#icon-listing
// The first table lists semantic identifiers for specific VS Code workbench locations; the second table lists the general Codicon identifiers intended for use by extensions.
export function getSnippetCategoryIconId(
  categoryName: string,
  catalogIconId: string | undefined,
): string {
  return (
    catalogIconId ?? DICT_SPECIAL_CATEGORY_ICON[categoryName] ?? STR_DEFAULT_CATEGORY_ICON
  );
}

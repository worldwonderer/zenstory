/**
 * Maps folder titles (zh/en) to their corresponding file types.
 * Used to determine what type of file to create inside a given folder.
 */
export const FOLDER_TYPE_MAP: Record<string, string> = {
  // Chinese folder names
  "设定": "lore",
  "场景": "lore",
  "角色": "character",
  "人物": "character",
  "大纲": "outline",
  "构思": "outline",
  "分集大纲": "outline",
  "素材": "snippet",
  "正文": "draft",
  "草稿": "draft",
  "剧本": "script",

  // English folder names
  "Lore": "lore",
  "World Building": "lore",
  "Scene": "lore",
  "Scenes": "lore",
  "Characters": "character",
  "Character": "character",
  "Outline": "outline",
  "Outlines": "outline",
  "Ideas": "outline",
  "Episode Outline": "outline",
  "Materials": "snippet",
  "Material": "snippet",
  "Draft": "draft",
  "Drafts": "draft",
  "Script": "script",
  "Scripts": "script",
};

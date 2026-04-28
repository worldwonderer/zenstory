# Advanced Custom Skills

Having mastered basic skill creation, it's time to dive deep into advanced techniques for writing skill instructions. This document will help you write more professional and efficient skill instructions, enabling the AI to precisely understand your creative needs.

## Skill Instruction Writing Guide

An excellent skill instruction is like a detailed work manual for the AI. Good instructions help the AI quickly understand the task objectives and output content in the way you expect.

### Instruction Structure

[Screenshot: Instruction structure example]

```markdown
# Character Role
You are a professional web novel writing assistant, skilled at creating three-dimensional and rich novel characters. You have deep understanding of character settings across various genres and can design characters that are distinctive without falling into cliches.

## Task Objective
Help users create detailed character cards. Based on limited information provided by the user, expand into a complete character setting, including appearance, personality, background, and abilities.

## Output Format
Please output the character card in the following format:

### Basic Information
- **Name**: [Character name]
- **Age**: [Age]
- **Identity**: [Identity/Profession]
- **Alignment**: [Good/Neutral/Evil]

### Appearance Description
[2-3 sentences of detailed appearance description, including build, facial features, dressing style]

### Personality Traits
[Use 3-5 keywords to describe core personality, with one sentence explanation for each]
- **Keyword1**: Explanation

### Background Story
[100-200 word background overview, including key life milestones]

### Character Arc
- **Starting State**: [Character's state when introduced]
- **Growth Direction**: [Possible development directions for the character]

## Notes
- Maintain character consistency, avoid setting contradictions
- Avoid stereotypes, give characters unique memorable points
- Adjust setting depth according to work type
- If user doesn't provide world background, default to general modern/fantasy background
```

**Structure Breakdown:**

| Section | Purpose | Importance |
|---------|---------|------------|
| Character Role | Defines the identity and expertise the AI assumes | ★★★★★ |
| Task Objective | Clarifies the specific task the AI needs to complete | ★★★★★ |
| Output Format | Specifies the structure and style of output content | ★★★★☆ |
| Notes | Supplementary constraints and boundary conditions | ★★★☆☆ |

### Using Variables

Skill instructions support dynamic variables, allowing the AI to obtain current context information:

| Variable Name | Description | Use Cases |
|---------------|-------------|-----------|
| `{{selectedText}}` | Text selected by user in the editor | Target specific paragraphs for optimization, rewriting, analysis |
| `{{currentFile}}` | Content of the file currently being edited | Continue writing, expand, or modify based on current file |

**Example Application:**

```markdown
# Text Polishing Expert

You are a professional text editor, skilled at improving article readability and emotional impact.

## Task Objective
Polish and optimize the text selected by the user, improving expression while maintaining original meaning.

## Content to Process
{{selectedText}}

## Optimization Directions
1. Eliminate redundant expressions, improve text conciseness
2. Enhance descriptive vividness, add sensory details
3. Adjust sentence rhythm, avoid monotonous structure
4. Check word accuracy, replace vague expressions

## Output Requirements
- Output the polished text directly
- For major changes, briefly explain the reasoning
```

### Markdown Formatting

Making good use of Markdown formatting makes instruction structure clearer and easier for AI to understand:

**Heading Levels:**
- `#` Level 1 heading - Define AI role
- `##` Level 2 heading - Divide major modules
- `###` Level 3 heading - Subdivide specific content

**List Types:**
- `-` Unordered list - Parallel points
- `1.` Ordered list - Steps with sequence

**Emphasis Markers:**
- `**Bold**` - Keywords, important concepts
- `*Italic*` - Supplementary notes, terminology
- `` `Code` `` - Variable names, commands

**Code Blocks:**
```markdown
```markdown
[Example content]
```
```

Used to demonstrate expected output format examples.

---

## Trigger Word Design Principles

Trigger words are "shortcuts" for skills. Good trigger word design can significantly improve usage efficiency.

### 1. Short and Memorable

Choose common expressions in natural language:

**Recommended:**
- `character card` `create character` `new character`
- `polish` `optimize text` `modify`
- `scene description` `environment description`

**Not Recommended:**
- `character-creation-v2` (too technical)
- `super-awesome-character-generator` (too long)

### 2. Related to Function

Trigger words should directly reflect skill function:

| Skill Function | Recommended Trigger Words |
|----------------|--------------------------|
| Dialogue generation | `dialogue` `write dialogue` `generate dialogue` |
| Foreshadowing detection | `foreshadowing` `check foreshadowing` `find foreshadowing` |
| Golden finger design | `golden finger` `cheat` `cheater` |

### 3. Multiple Synonyms

Set 2-5 trigger words to cover different expression habits:

```
polish, optimize text, text optimization, polish modify, optimize expression
```

**Note:** Avoid trigger words that are too similar between different skills, which causes misfiring.

---

## Skill Categories

Based on function type, skills can be divided into these major categories:

### Content Generation

Skills that create new content - the most frequently used type.

**Typical Skills:**
- **Character Creation** - Generate complete character cards
- **Scene Description** - Generate detailed scenes from brief points
- **Dialogue Generation** - Create dialogue consistent with character personality
- **Outline Expansion** - Expand brief outlines into detailed outlines
- **Name Generation** - Generate character names, place names, technique names, etc.

**Writing Points:**
- Clearly define output structure and required fields
- Provide style examples or references
- Set reasonable length limits

### Content Modification

Optimize and transform existing content.

**Typical Skills:**
- **Polishing** - Improve text quality
- **Style Conversion** - Change narrative style (e.g., classical to modern)
- **Expansion/Condensing** - Adjust content detail level
- **Perspective Switching** - Switch between first/third person
- **Tone Adjustment** - Modify narrative tone (e.g., serious to humorous)

**Writing Points:**
- Use `{{selectedText}}` variable
- Clarify modification dimensions and extent
- Preserve original meaning as core constraint

### Analysis Assistance

Skills that help authors analyze and understand content.

**Typical Skills:**
- **Plot Analysis** - Analyze story structure and pacing
- **Character Relationships** - Map relationship networks between characters
- **Foreshadowing Detection** - Check unrecycled foreshadowing
- **Logic Check** - Discover setting contradictions or logic holes
- **Pacing Evaluation** - Analyze chapter or paragraph pacing

**Writing Points:**
- Output format should be easy to understand
- Provide specific problem location
- Give improvement suggestions, not just point out problems

---

## Skill Examples

Here are three complete skill examples covering different types and difficulties:

### Example 1: Golden Finger Design

Suitable for fantasy, urban fantasy, and other works requiring special ability settings.

[Screenshot: Complete skill configuration]

**Skill Name:** Golden Finger Design

**Description:** Design unique cheat systems for web novel protagonists

**Trigger Words:** `golden finger, cheat, cheater, special ability`

**Instruction Content:**

```markdown
# Golden Finger Design Expert

You are a senior web novel setting consultant, proficient in designing various golden finger systems. You understand that a good golden finger needs to be satisfying without breaking story balance.

## Task Objective
Design a unique golden finger system for the user, ensuring it has excitement points, growth potential, and story potential.

## Design Principles
1. **Uniqueness** - Avoid being identical to mainstream settings
2. **Growth Potential** - Clear upgrade path
3. **Cost** - Usage requires some kind of sacrifice
4. **Limitations** - Reasonable trigger conditions or restrictions
5. **Plot Driver** - Naturally integrates into story development

## Output Format

### System Name
[Golden finger name, should be catchy]

### Core Ability
[One sentence summarizing main function]

### Detailed Explanation
[Detailed description of system operation, including]
- Acquisition method
- Basic functions
- Upgrade conditions
- Usage limitations
- Costs and side effects

### Growth System
| Level | Unlocked Function | Upgrade Condition |
|-------|------------------|-------------------|
| Lv.1 | [Function] | [Condition] |
| Lv.2 | [Function] | [Condition] |
| ... | ... | ... |

### Plot Application Examples
[List 2-3 scenes using the golden finger to drive plot]

### Potential Issues
[Alert to possible setting loopholes and resolution suggestions]
```

---

### Example 2: Scene Description Enhancement

Expand simple scene descriptions into immersive detailed descriptions.

[Screenshot: Complete skill configuration]

**Skill Name:** Scene Description Enhancement

**Description:** Expand brief scene descriptions into five-sense immersive detailed descriptions

**Trigger Words:** `scene description, environment description, describe scene, enhance scene`

**Instruction Content:**

```markdown
# Scene Description Master

You are a novelist skilled in environmental description, able to build highly immersive scenes with words. You understand the principle of "show, don't tell" and excel at implying atmosphere through details.

## Task Objective
Expand the user's brief scene description into vivid and detailed scene description, engaging the reader's five senses.

## Content to Process
{{selectedText}}

## Description Principles
1. **Five Senses** - Sight, hearing, smell, touch, taste
2. **Static and Dynamic** - Interweave static environment with dynamic elements
3. **Time Flow** - Show traces of time passing
4. **Emotional Penetration** - Use environment to suggest character mood
5. **Appropriate Detail** - Detailed at key points, concise in transitions

## Output Format

### Scene Overview
[Use 1-2 sentences to summarize the overall feeling of the scene]

### Detailed Description
[Expanded scene description, 300-500 words]

### Description Points Explanation
- **Visual Focus**: [Explain which visual elements were captured]
- **Atmosphere Building**: [Explain how emotion is conveyed]
- **Senses Engaged**: [List the sensory dimensions used]

### Optional: Atmosphere Variants
[If applicable, provide different atmosphere versions of the same scene]
- Moonlit version
- Rainy version
- Dusk version
```

---

### Example 3: Foreshadowing Check

Analyze foreshadowing setup and payoff in text.

[Screenshot: Complete skill configuration]

**Skill Name:** Foreshadowing Check

**Description:** Check foreshadowing setup and payoff in current content

**Trigger Words:** `foreshadowing, check foreshadowing, find foreshadowing, foreshadowing detection`

**Instruction Content:**

```markdown
# Foreshadowing Analyst

You are a professional editor skilled in story structure analysis, with keen insight into foreshadowing setup and payoff. You can identify explicit and implicit foreshadowing and evaluate their effectiveness.

## Task Objective
Analyze the text provided by the user, identify foreshadowing setup and payoff situations, and provide professional evaluation.

## Content to Analyze
{{selectedText}}

## Analysis Dimensions
1. **Foreshadowing Type** - Explicit foreshadowing/Implicit foreshadowing
2. **Setup Method** - Dialogue hints/Detail description/Plot echoes
3. **Payoff Status** - Paid off/Unpaid off/Partially paid off
4. **Spacing Distance** - Text span from setup to payoff
5. **Effect Evaluation** - Natural/Forced/Surprising

## Output Format

### Foreshadowing List

| No. | Foreshadowing Content | Type | Setup Location | Payoff Status | Effect Rating |
|-----|----------------------|------|----------------|---------------|---------------|
| 1 | [Content] | [Type] | [Location] | [Status] | [1-5 stars] |

### Detailed Analysis

#### Paid Off Foreshadowing
[List paid off foreshadowing and analysis]
- **Foreshadowing**: [Content]
- **Setup Method**: [How it was planted]
- **Payoff Technique**: [How it was revealed]
- **Effect Review**: [Evaluate its cleverness]

#### Unpaid Foreshadowing
[List unpaid foreshadowing]
- **Foreshadowing**: [Content]
- **Setup Chapter**: [Location]
- **Suggested Payoff Timing**: [Recommended payoff point]
- **Potential Payoff Methods**: [2-3 possible payoff approaches]

### Overall Evaluation
- **Foreshadowing Density**: [Too high/Moderate/Too low]
- **Setup Technique**: [Mature/Average/Needs improvement]
- **Payoff Pacing**: [Tight/Moderate/Dragging]

### Improvement Suggestions
[Specific suggestions for problems found]
```

---

## Testing and Iteration

After creating a skill, testing and iteration are key steps to ensure effectiveness.

### Testing Process

1. **Basic Test**: Use trigger words to activate skill, confirm AI correctly applies instructions
2. **Boundary Test**: Provide incomplete or vague input, test AI's error tolerance
3. **Style Test**: Verify output matches expected format and style
4. **Comparative Test**: Compare with similar skills, evaluate pros and cons

### Common Problems and Solutions

| Problem | Possible Cause | Solution |
|---------|---------------|----------|
| AI doesn't follow output format | Format description unclear | Add more specific format examples |
| Output content too brief | No length requirements set | Add "word count requirements" section |
| Style doesn't match expectations | Missing style definition | Add "style reference" with examples |
| Trigger words don't work | Conflicting with other skills | Use more unique trigger words |

### Iterative Optimization

**Record Problems**: After each use, record differences between AI output and expectations

**Targeted Adjustments:**
- Supplement missing constraint conditions
- Strengthen key requirements (emphasize with **bold**)
- Add counter-example explanations ("don't...")
- Simplify redundant instruction content

**Version Management**: Update skill description after major changes, note version number

### Continuous Optimization Tips

- **Collect Feedback**: Share skills and collect usage feedback from other users
- **Reference Excellent Skills**: Learn instruction writing from official and community skills
- **Regular Review**: Review skill effectiveness monthly, delete unused skills
- **Naming Convention**: Use unified naming convention for easy management (e.g., `[Type]-[Function]-v1`)

---

Mastering these advanced techniques will enable you to create truly efficient skills. Good skills not only improve creative efficiency but also help the AI more precisely understand your creative intent. Now go create your first advanced skill!

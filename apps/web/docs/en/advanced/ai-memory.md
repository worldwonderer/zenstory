# AI Memory & Context

AI Memory is one of the core features of zenstory Novel Writing Workbench. It serves as a "project dossier" for your AI assistant, enabling the AI to continuously understand your work's settings, writing style, and creative progress, ensuring consistency and professionalism in every conversation.

---

## What is AI Memory?

AI Memory is a project-level persistent information storage. Unlike temporary conversations, content in AI Memory is automatically referenced in **all conversations**, ensuring the AI always understands the full scope of your work.

**Core Benefits:**
- **Consistency Assurance** - The AI won't forget your settings, styles, and preferences
- **No Repetition** - No need to re-explain background in every conversation
- **Intelligent Context** - The AI can provide more precise suggestions based on the project's overall context
- **Dynamic Updates** - Can be automatically updated by AI during conversations (with your confirmation)

**Typical Use Cases:**
- Recording the novel's genre (fantasy, urban, sci-fi, etc.)
- Defining the protagonist's personality traits and growth trajectory
- Setting the writing style (humorous, serious, action-packed, etc.)
- Tracking current creative progress
- Noting important setting details to remember

---

## Opening AI Memory

[Screenshot: Database icon button in the right chat panel header bar, with "AI Memory" tooltip on hover]

**Steps:**
1. Enter any project's editing interface
2. Find the database icon in the right chat panel's header bar
3. Click the icon to open the "AI Memory" dialog

**Location Tips:**
- The icon is located on the right side of the chat panel header
- To the left of the "New Chat" button (+)
- Hovering shows the "AI Memory" tooltip

**Quick Tips:**
- Desktop: The icon is small, look for the database-shaped button
- Mobile: Button size is adapted for touch, easier to tap

---

## AI Memory Content Details

The AI Memory dialog contains four core modules, each with specific purposes and filling recommendations.

### Project Overview

[Screenshot: Project Overview input box showing multi-line text editing area, with placeholder text "Describe the novel's genre, world setting, protagonist setup, and other core information"]

**Content to Fill:**
- **Work Type** - Web novel, short story, serialized novel, etc.
- **World Setting Overview** - Cultivation world, modern urban, sci-fi future, etc.
- **Protagonist Setup** - Name, core traits, main goals
- **Core Conflict** - The main conflict and themes of the story
- **Target Audience** - Expected reader demographic

**Example:**
> This is an Eastern fantasy cultivation novel, set in a xianxia world of three realms and nine domains. The protagonist Lin Feng is a young man with a special constitution, raised by a mysterious elder. The story's core is the protagonist's journey from mortal to powerful cultivator, with a hot-blooded, satisfying style targeting male web novel readers aged 18-30. Main attractions are the leveling system, sect competitions, and treasure hunts.

**Best Practices:**
- The more detailed, the better - don't worry about writing too much
- Include key proper nouns (faction names, technique names, etc.)
- Clearly define the work's positioning and style
- Can be updated anytime; recommend filling carefully at project start

---

### Writing Style

[Screenshot: Writing Style input box showing 2-line text editing area, with placeholder text "Describe language style, narrative pacing, writing characteristics, etc."]

**Content to Fill:**
- **Language Style** - Lighthearted humor, serious depth, passionate intensity, etc.
- **Narrative Pacing** - Fast-paced, slow burn, balanced tension, etc.
- **Writing Characteristics** - Concise, flowery, colloquial, classical style, etc.
- **Reference Authors** - If you have writers you're emulating, mention them
- **Special Requirements** - Things to avoid, elements that must be included, etc.

**Example:**
> Lighthearted and humorous language, using internet slang and memes frequently. Dialogue should be concise and punchy. Fast narrative pacing with satisfying moments or cliffhangers in every chapter. Avoid excessive psychological descriptions and scenery descriptions; drive the plot through action and dialogue. Reference style: Mao Ni's humor + Tang Jia San Shao's pacing.

**Best Practices:**
- If you like a particular author's style, write it explicitly
- Note your writing weaknesses (e.g., "not good at writing fight scenes")
- State your strengths (e.g., "good at writing plot twists")
- You can include links to representative works

---

### Current Stage

[Screenshot: Current Stage input box showing 2-line text editing area, with placeholder text "Explain current writing progress and stage goals"]

**Content to Fill:**
- **Writing Progress** - Which chapter/volume you're currently writing
- **Current Goal** - Tasks to complete at this stage
- **Key Content** - Plot lines currently being handled
- **Problems Encountered** - Creative bottlenecks or issues to resolve

**Example:**
> Currently writing Chapter 7 of Volume 1, the protagonist just entered the sect. This stage's goal is to complete the sect trial arc (about 10 chapters), focusing on depicting the protagonist showcasing talent during trials, making companions, and obtaining the first fortuitous encounter. Current problem: trial level designs lack novelty, need more creativity.

**Best Practices:**
- Update regularly (recommend updating after completing each important milestone)
- Clearly state short-term goals to help AI understand current focus
- Record creative difficulties encountered; AI may offer suggestions
- Can include expected completion dates

---

### Notes

[Screenshot: Notes input box showing 3-line text editing area, with placeholder text "Record writing key points, matters needing attention, problems to solve, etc."]

**Content to Fill:**
- **Important Settings** - Details easy to forget or confuse
- **Writing Points** - Creative principles for self-reminder
- **Things to Avoid** - Mistakes that must not be made
- **Unresolved Issues** - Settings not yet decided
- **Inspiration Fragments** - Plots you want to add but haven't scheduled yet

**Example:**
> Important setting: The protagonist's golden finger is a "time perception" ability, but each use consumes lifespan - this setting should run throughout the text. Avoid: Don't make the protagonist too overpowered; maintain appropriate setbacks. Unresolved: The main villain's motivation isn't sufficient yet, needs refinement. Inspiration fragment: Want to add a "secret realm exploration" arc in the middle section, located in underwater ruins.

**Best Practices:**
- This is a "memo" - write down whatever comes to mind
- Can use list format for AI to quickly understand
- Regularly clean up resolved issues
- Important foreshadowing can be noted here for self-reminder

---

## How AI Uses Memory

AI Memory content is automatically passed to the AI during each conversation, becoming important context for the AI to understand your project.

### Automatic Reference Mechanism

When you send a message to the AI, the system automatically appends AI Memory content to your message context:

```
Your message: "Help me design the plot for Chapter 3"

Complete context received by AI:
- [AI Memory]
  - Project Overview: Eastern fantasy cultivation novel...
  - Writing Style: Lighthearted humor, fast pacing...
  - Current Stage: Writing Volume 1 Chapter 7...
  - Notes: Protagonist's golden finger is time perception...
- [Your Message] Help me design the plot for Chapter 3
```

This means when designing plots, the AI will automatically consider:
- The work's overall style and positioning
- The protagonist's ability settings and limitations
- Current creative progress and goals
- Notes and things to avoid that you've recorded

### Maintaining Creative Consistency

**Example Scenario:**
You defined in AI Memory: "Using the time perception ability consumes the protagonist's lifespan."

**Without AI Memory:**
```
You: Help me write a battle scene for the protagonist
AI: [Generates battle where protagonist uses time perception unlimitedly, completely unharmed]
You: That's wrong, using this ability consumes lifespan
AI: Sorry, let me regenerate...
```

**With AI Memory:**
```
You: Help me write a battle scene for the protagonist
AI: [Automatically considers lifespan consumption setting, generates battle where protagonist uses ability cautiously, weighing pros and cons]
```

### AI Auto-Update (Requires Confirmation)

In some conversations, the AI may suggest updating AI Memory content:

[Screenshot: AI conversation showing "I suggest updating your AI Memory: Current Stage from 'Volume 1 Chapter 7' to 'Volume 1 Chapter 8'", with "Agree"/"Decline" buttons below]

**Typical Update Scenarios:**
- You completed a creative stage, AI suggests updating "Current Stage"
- AI discovered a setting conflict, suggests correcting "Project Overview"
- Your writing style has adjusted, AI suggests updating "Writing Style"

**Handling Options:**
- Agree: AI Memory updates immediately
- Decline: Keep original content unchanged
- Manual Edit: You can also open the AI Memory dialog yourself to edit

---

## Editing AI Memory

You can manually edit AI Memory content at any time.

### Editing Operations

[Screenshot: AI Memory dialog editing interface showing four text input boxes and "Cancel"/"Save" buttons at the bottom]

**Steps:**
1. Open the AI Memory dialog
2. Directly modify content in any input box
3. Click the "Save" button at the bottom
4. Changes take effect immediately

**Notes:**
- Only clicking "Save" will save changes
- Clicking "Cancel" discards all modifications
- If no changes are made, the "Save" button remains disabled
- Loading animation displays while saving, dialog auto-closes when complete

### Modification Suggestions

**When to Update AI Memory:**
- When starting a new project, fill all fields completely
- When completing an important creative milestone, update "Current Stage"
- When discovering setting errors or needing adjustments, modify relevant fields
- When getting new inspiration or clarifying new requirements, add to "Notes"

**Update Frequency Recommendations:**
- Project Overview: Fill in detail initially, occasionally supplement later
- Writing Style: Fill at project start, rarely changes afterward
- Current Stage: Update weekly or after completing each major chapter
- Notes: Add anytime, regularly clean up resolved issues

---

## Best Practices

### 1. Fill Completely at Project Start

**Recommended Action:**
After creating a new project, the first thing to do is open AI Memory and carefully fill each field.

**Reasons:**
- The more complete the initial information, the more precise the AI's subsequent suggestions
- Avoid repeatedly explaining basic settings in conversations
- Helps you clarify your creative vision

**Checklist:**
- [ ] Project Overview: Includes genre, world setting, protagonist, core conflict
- [ ] Writing Style: Clear language style, pacing, reference objects
- [ ] Current Stage: Write "Project starting, currently brainstorming outline"
- [ ] Notes: Record initial inspirations and ideas

---

### 2. Regularly Update Current Stage

**Recommended Frequency:** Every 3-5 chapters completed, or after completing an important plot segment

**Update Template:**
```
[Time] YYYY-MM-DD
[Progress] Currently writing Chapter X/Volume X
[Goal] To complete XXX at this stage (approximately Y chapters)
[Focus] Currently handling XXX plot line
[Issue] Current difficulty: XXX
```

**Benefits:**
- AI can provide suggestions more aligned with current progress
- Helps you maintain creative rhythm
- Forms a creative log for easy review

---

### 3. Record Important Setting Decisions in Notes

**Content to Record:**
- Detail settings easy to forget
- Important foreshadowing and hints
- Pitfalls to avoid
- Unresolved questions temporarily undecided

**Example:**
> [Setting] The protagonist's master is actually the main villain, this twist is revealed in Chapter 50, need to plant foreshadowing early on
> [Avoid] Don't write the female lead as a vase; give her independent growth arc
> [Pending] The Volume 3 villain isn't decided yet, need to design an opponent whose abilities counter the protagonist

---

### 4. Use AI Memory to Resolve Setting Conflicts

**Problem Scenario:**
You wrote "protagonist uses time perception for the first time" in Chapter 10, but when writing Chapter 30, you forgot and wrote "first time using" again.

**Solution:**
Clearly record in AI Memory's "Notes":
> [Ability] Time perception first used in Chapter 10, upgraded to level 2 in Chapter 20, comprehended time stop in Chapter 35

**AI's Role:**
When writing relevant chapters, the AI will reference the notes and remind you of the ability's usage history, avoiding contradictions.

---

### 5. Let AI Help Improve AI Memory

**Conversation Example:**
```
You: I created a new project but don't know how to fill AI Memory. Can you help?
AI: Of course! Please tell me your work type, protagonist setup, and core selling points, and I'll help generate a complete AI Memory draft.
You: [Provide basic information]
AI: Based on your description, I suggest filling it this way:
     Project Overview: ...
     Writing Style: ...
     Current Stage: ...
     Notes: ...
     How does that look? Need modifications?
```

**Benefits:**
- AI excels at structured expression and can help organize your thoughts
- AI will supplement dimensions you might overlook based on your description
- Generated drafts can be directly copied into AI Memory

---

### 6. Regular Review and Cleanup

**Recommended Frequency:** Monthly or after completing each volume

**Review Content:**
- Project Overview: Any new confirmed settings to add?
- Writing Style: Any new style preferences?
- Current Stage: Is it outdated?
- Notes: Any resolved issues that can be deleted?

**Benefits:**
- Maintain AI Memory accuracy and conciseness
- Avoid outdated information interfering with AI's judgment
- Form a complete record of project evolution

---

## Common Questions

### Q: What's the difference between AI Memory and conversation history?

**A:**
- **AI Memory** - Project-level persistent information, referenced in all conversations
- **Conversation History** - Temporary records of a single session, cleared when starting a new session

Analogy: AI Memory is your "personal file," conversation history is "chat logs."

---

### Q: Will AI Memory content being too long cause issues?

**A:** No issues. AI Memory content counts toward context token budget, but the system manages it intelligently. Recommendations:
- Project Overview can be detailed (suggest under 500 words)
- Other fields stay concise (suggest under 200 words each)
- Total length best kept under 1500 words

---

### Q: I don't want the AI to see certain information, what should I do?

**A:** Don't fill it in AI Memory. AI Memory content is **referenced in all conversations**. If you want certain information mentioned only in specific conversations, it's recommended to:
- Tell the AI directly during conversation (don't write to AI Memory)
- Or state at conversation start: "Don't consider the XXX setting for this conversation"

---

### Q: Does AI Memory auto-save?

**A:** No. You must manually click the "Save" button for changes to take effect. This prevents accidental operations. If you close the dialog without saving, there will be a prompt.

---

### Q: In collaborative projects, is AI Memory shared?

**A:** Yes. AI Memory is project-level; all collaborators on the same project see the same AI Memory content. Recommendations:
- Primary creator responsible for maintaining AI Memory
- Confirm settings and style together before collaborating
- Communicate before major changes

---

### Q: Can AI Memory be exported or backed up?

**A:** Currently AI Memory is stored in the database and doesn't support individual export. For backup, it's recommended to:
- Manually copy content to local documents
- Periodically save screenshots
- Use the project's complete export function (includes AI Memory)

---

## Summary

AI Memory is the "project brain" of the zenstory platform, enabling the AI to continuously and consistently understand your creative intent. Mastering AI Memory usage will significantly improve your creative efficiency:

**Key Points:**
- Fill completely at project start to avoid repeated explanations later
- Regularly update current stage to help AI provide precise suggestions
- Record important settings in notes to prevent contradictions
- Utilize AI to help improve, making settings more systematic

**Next Steps:**
- Open your project, check if AI Memory is complete
- Optimize each field's content based on this article's recommendations
- Observe in your next AI conversation whether the AI better understands your needs

Start using AI Memory to make your creative journey smoother!

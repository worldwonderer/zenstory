import { describe, expect, it } from "vitest";

import { buildTodayActionPlan } from "../dashboardActionPlan";

const t = (key: string, options?: { defaultValue?: string }) => {
  const table: Record<string, string> = {
    "activationGuide.steps.project_created": "创建项目",
    "todayActionPlan.personaRecommendations.persona_explorer_template.title": "探索型模板推荐",
    "todayActionPlan.personaRecommendations.persona_explorer_template.description":
      "优先给你开放灵感模板和快速起稿入口。",
  };
  return table[key] ?? options?.defaultValue ?? key;
};

describe("buildTodayActionPlan", () => {
  it("builds a 3-step plan and prioritizes activation + persona recommendations", () => {
    const plan = buildTodayActionPlan({
      activationGuide: {
        user_id: "u-1",
        window_hours: 24,
        within_first_day: true,
        total_steps: 4,
        completed_steps: 1,
        completion_rate: 0.25,
        is_activated: false,
        next_event_name: "project_created",
        next_action: "/dashboard",
        steps: [
          {
            event_name: "signup_success",
            label: "Signup",
            completed: true,
            completed_at: "2026-03-08T00:00:00Z",
            action_path: "/dashboard",
          },
          {
            event_name: "project_created",
            label: "Create project",
            completed: false,
            completed_at: null,
            action_path: "/dashboard",
          },
        ],
      },
      personaRecommendations: [
        {
          id: "persona_explorer_template",
          title: "探索型模板推荐",
          description: "优先给你开放灵感模板和快速起稿入口。",
          action: "/dashboard/inspirations",
        },
      ],
      projectsCount: 0,
      latestProjectId: null,
      activeProjectType: "novel",
      t,
    });

    expect(plan).toHaveLength(3);
    expect(plan[0].title).toBe("创建项目");
    expect(plan[0].action.type).toBe("create_project");
    expect(plan[1].title).toBe("探索型模板推荐");
    expect(plan[2].id).toBe("fallback-upgrade");
  });

  it("falls back to open/export/upgrade chain when project exists", () => {
    const plan = buildTodayActionPlan({
      activationGuide: null,
      personaRecommendations: [],
      projectsCount: 2,
      latestProjectId: "project-1",
      activeProjectType: "novel",
      t,
    });

    expect(plan).toHaveLength(3);
    expect(plan[0].action).toEqual({ type: "navigate", path: "/project/project-1" });
    expect(plan[1].action).toEqual({ type: "navigate", path: "/project/project-1" });
    expect(plan[2].action).toEqual({
      type: "navigate",
      path: "/dashboard/billing?source=dashboard_today_action",
    });
  });
});

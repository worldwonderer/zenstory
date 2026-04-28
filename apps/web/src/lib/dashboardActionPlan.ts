import { buildUpgradeUrl } from "../config/upgradeExperience";
import type { ProjectType } from "../types";
import type { PersonaRecommendation } from "./onboardingPersonaApi";
import type { ActivationGuideResponse } from "../types/writingStats";

type TranslateFn = (key: string, options?: { defaultValue?: string; [key: string]: unknown }) => string;

export type TodayActionPlanAction =
  | {
      type: "navigate";
      path: string;
    }
  | {
      type: "create_project";
      projectType: ProjectType;
    };

export interface TodayActionPlanItem {
  id: string;
  title: string;
  description: string;
  ctaLabel: string;
  action: TodayActionPlanAction;
}

interface BuildTodayActionPlanInput {
  activationGuide: ActivationGuideResponse | null;
  personaRecommendations: PersonaRecommendation[];
  projectsCount: number;
  latestProjectId: string | null;
  activeProjectType: ProjectType;
  t: TranslateFn;
}

function normalizeActionPath(path: string | null | undefined, fallback = "/dashboard"): string {
  const value = (path ?? "").trim();
  return value || fallback;
}

function createActionId(item: TodayActionPlanItem): string {
  return `${item.id}:${item.action.type}:${item.action.type === "navigate" ? item.action.path : item.action.projectType}`;
}

function resolveActivationStepTitle(
  eventName: string,
  fallbackLabel: string,
  t: TranslateFn,
): string {
  return t(`activationGuide.steps.${eventName}`, { defaultValue: fallbackLabel });
}

function resolveActivationStepAction({
  eventName,
  stepActionPath,
  activationNextAction,
  latestProjectId,
  activeProjectType,
}: {
  eventName: string;
  stepActionPath: string | null | undefined;
  activationNextAction: string | null | undefined;
  latestProjectId: string | null;
  activeProjectType: ProjectType;
}): TodayActionPlanAction {
  if (eventName === "project_created") {
    return {
      type: "create_project",
      projectType: activeProjectType,
    };
  }

  if (eventName === "first_file_saved" || eventName === "first_ai_action_accepted") {
    if (latestProjectId) {
      return {
        type: "navigate",
        path: `/project/${latestProjectId}`,
      };
    }
  }

  return {
    type: "navigate",
    path: normalizeActionPath(stepActionPath, activationNextAction ?? "/dashboard"),
  };
}

function resolvePersonaRecommendationTitle(
  recommendation: PersonaRecommendation,
  t: TranslateFn,
): string {
  return t(`todayActionPlan.personaRecommendations.${recommendation.id}.title`, {
    defaultValue: recommendation.title,
  });
}

function resolvePersonaRecommendationDescription(
  recommendation: PersonaRecommendation,
  t: TranslateFn,
): string {
  const fallback = recommendation.description
    || t("todayActionPlan.personaDescription", {
      defaultValue: "基于你的偏好推荐的下一步动作。",
    });

  return t(`todayActionPlan.personaRecommendations.${recommendation.id}.description`, {
    defaultValue: fallback,
  });
}

function resolvePersonaRecommendationActionPath(
  recommendation: PersonaRecommendation,
): string {
  const raw = normalizeActionPath(recommendation.action, "/dashboard");
  if (raw !== "/dashboard") {
    return raw;
  }

  // Avoid no-op navigation (/dashboard -> /dashboard). Provide sensible fallbacks.
  const fallbackById: Record<string, string> = {
    persona_serial_streak: "/dashboard/projects",
    goal_quality_review: "/dashboard/projects",
    goal_habit_activation: "/dashboard/projects",
    level_beginner_path: "/dashboard/inspirations",
  };

  return fallbackById[recommendation.id] || "/dashboard/projects";
}

export function buildTodayActionPlan({
  activationGuide,
  personaRecommendations,
  projectsCount,
  latestProjectId,
  activeProjectType,
  t,
}: BuildTodayActionPlanInput): TodayActionPlanItem[] {
  const candidates: TodayActionPlanItem[] = [];
  const ctaLabel = t("todayActionPlan.cta", { defaultValue: "一键执行" });

  const pendingActivationSteps = activationGuide?.within_first_day
    ? activationGuide.steps?.filter((step) => !step.completed) ?? []
    : [];
  const hasPendingActivationSteps = pendingActivationSteps.length > 0;
  const hasPendingActivationProjectStep = pendingActivationSteps.some(
    (step) => step.event_name === "project_created",
  );

  for (const step of pendingActivationSteps) {
    candidates.push({
      id: `activation-${step.event_name}`,
      title: resolveActivationStepTitle(step.event_name, step.label, t),
      description: t("todayActionPlan.activationDescription", {
        defaultValue: "完成该里程碑，解锁更顺畅的创作流程。",
      }),
      ctaLabel,
      action: resolveActivationStepAction({
        eventName: step.event_name,
        stepActionPath: step.action_path,
        activationNextAction: activationGuide?.next_action,
        latestProjectId,
        activeProjectType,
      }),
    });
  }

  for (const recommendation of personaRecommendations) {
    candidates.push({
      id: `persona-${recommendation.id}`,
      title: resolvePersonaRecommendationTitle(recommendation, t),
      description: resolvePersonaRecommendationDescription(recommendation, t),
      ctaLabel,
      action: {
        type: "navigate",
        path: resolvePersonaRecommendationActionPath(recommendation),
      },
    });
  }

  if (!hasPendingActivationSteps && projectsCount === 0 && !hasPendingActivationProjectStep) {
    candidates.push({
      id: "fallback-create-project",
      title: t("todayActionPlan.defaults.createProject.title", {
        defaultValue: "创建你的首个项目",
      }),
      description: t("todayActionPlan.defaults.createProject.description", {
        defaultValue: "先把灵感落到项目里，后续写作与导出都会更顺畅。",
      }),
      ctaLabel: t("todayActionPlan.defaults.createProject.cta", {
        defaultValue: "一键建项目",
      }),
      action: {
        type: "create_project",
        projectType: activeProjectType,
      },
    });
  } else if (!hasPendingActivationSteps && latestProjectId) {
    candidates.push({
      id: "fallback-open-project",
      title: t("todayActionPlan.defaults.openProject.title", {
        defaultValue: "继续最近项目",
      }),
      description: t("todayActionPlan.defaults.openProject.description", {
        defaultValue: "延续上下文继续写，效率最高。",
      }),
      ctaLabel,
      action: {
        type: "navigate",
        path: `/project/${latestProjectId}`,
      },
    });
    candidates.push({
      id: "fallback-export-project",
      title: t("todayActionPlan.defaults.exportProject.title", {
        defaultValue: "验证导出链路",
      }),
      description: t("todayActionPlan.defaults.exportProject.description", {
        defaultValue: "打开项目后可直接点击“导出”，快速完成交付检查。",
      }),
      ctaLabel: t("todayActionPlan.defaults.exportProject.cta", {
        defaultValue: "去项目导出",
      }),
      action: {
        type: "navigate",
        path: `/project/${latestProjectId}`,
      },
    });
  }

  candidates.push({
    id: "fallback-upgrade",
    title: t("todayActionPlan.defaults.upgrade.title", {
      defaultValue: "查看升级权益",
    }),
    description: t("todayActionPlan.defaults.upgrade.description", {
      defaultValue: "提前确认配额和导出能力，避免创作中断。",
    }),
    ctaLabel: t("todayActionPlan.defaults.upgrade.cta", {
      defaultValue: "去升级页",
    }),
    action: {
      type: "navigate",
      path: buildUpgradeUrl("/dashboard/billing", "dashboard_today_action"),
    },
  });

  candidates.push({
    id: "fallback-inspirations",
    title: t("todayActionPlan.defaults.inspirations.title", {
      defaultValue: "补充灵感素材",
    }),
    description: t("todayActionPlan.defaults.inspirations.description", {
      defaultValue: "浏览精选灵感，快速补齐创作输入。",
    }),
    ctaLabel,
    action: {
      type: "navigate",
      path: "/dashboard/inspirations",
    },
  });

  const uniqueItems: TodayActionPlanItem[] = [];
  const seen = new Set<string>();
  for (const item of candidates) {
    const uniqueId = createActionId(item);
    if (seen.has(uniqueId)) {
      continue;
    }
    seen.add(uniqueId);
    uniqueItems.push(item);
  }

  return uniqueItems.slice(0, 3);
}

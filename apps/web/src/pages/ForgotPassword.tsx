import { Link, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { LogoMark } from "../components/Logo";
import { Mail } from "../components/icons";
import { PublicHeader } from "../components/PublicHeader";
import { authConfig } from "../config/auth";

export default function ForgotPassword() {
  const { t } = useTranslation(["auth"]);

  if (!authConfig.forgotPasswordEnabled) {
    return <Navigate to="/login" replace />;
  }

  const supportEmail = t("auth:forgotPassword.supportEmail", "support@zenstory.ai");

  return (
    <div className="min-h-screen bg-[hsl(var(--bg-primary))] flex flex-col">
      <PublicHeader variant="auth" maxWidth="max-w-6xl" />

      <div className="flex-1 flex items-center justify-center p-4 sm:p-6">
        <div className="w-full max-w-md">
          <div className="text-center mb-8 sm:mb-10">
            <div className="inline-flex items-center gap-2.5 mb-4">
              <div className="w-12 h-12 rounded-xl bg-[hsl(var(--accent-primary))] flex items-center justify-center shadow-lg">
                <LogoMark className="w-7 h-7 text-white" />
              </div>
            </div>
            <h1 className="text-2xl font-bold text-[hsl(var(--text-primary))] mb-2">
              {t("auth:forgotPassword.title")}
            </h1>
            <p className="text-[hsl(var(--text-secondary))] text-sm">
              {t("auth:forgotPassword.subtitle")}
            </p>
          </div>

          <div className="bg-[hsl(var(--bg-secondary))] rounded-2xl p-6 sm:p-8 shadow-lg border border-[hsl(var(--border-color))]">
            <div className="rounded-xl border border-[hsl(var(--accent-primary)/0.25)] bg-[hsl(var(--accent-primary)/0.08)] p-4 mb-6">
              <div className="flex items-start gap-3">
                <Mail className="w-5 h-5 text-[hsl(var(--accent-primary))] mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm text-[hsl(var(--text-primary))] font-medium">
                    {t("auth:forgotPassword.contactSupportTitle")}
                  </p>
                  <p className="text-xs text-[hsl(var(--text-secondary))] mt-1">
                    {t("auth:forgotPassword.contactSupportHint")}
                  </p>
                </div>
              </div>
            </div>

            <a
              href={`mailto:${supportEmail}`}
              className="btn-primary w-full py-3 text-base inline-flex items-center justify-center"
            >
              {t("auth:forgotPassword.contactSupportAction")}
            </a>

            <div className="mt-6 text-center">
              <Link
                to="/login"
                className="text-sm text-[hsl(var(--text-secondary))] hover:text-[hsl(var(--text-primary))] transition-colors"
              >
                {t("auth:login.backToLogin")}
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

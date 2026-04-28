import React from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Shield } from "lucide-react";
import { UserAvatar } from "../UserMenu";
import { useAuth } from "../../contexts/AuthContext";
import { useTranslation } from "react-i18next";

interface AdminHeaderProps {
  onMenuClick: () => void;
}

export const AdminHeader: React.FC<AdminHeaderProps> = ({ onMenuClick }) => {
  const navigate = useNavigate();
  const { t } = useTranslation("admin");
  const { user } = useAuth();

  const handleBackToApp = () => {
    navigate("/dashboard");
  };

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-[hsl(var(--separator-color))] bg-[linear-gradient(180deg,hsl(var(--bg-secondary)/0.96),hsl(var(--bg-secondary)/0.84))] px-3 shadow-[0_1px_0_hsl(var(--separator-color)),0_8px_24px_hsl(0_0%_0%_/_0.12)] backdrop-blur-xl sm:px-4">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          className="rounded-lg p-2 text-[hsl(var(--text-primary))] transition-colors hover:bg-[hsl(var(--bg-tertiary))] md:hidden"
          aria-label="Toggle menu"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>

        <div className="flex items-center gap-2">
          <button
            onClick={handleBackToApp}
            className="hidden items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-[hsl(var(--text-secondary))] transition-colors hover:bg-[hsl(var(--bg-tertiary))] sm:flex"
            title={t("header.backToApp", "返回应用")}
          >
            <ArrowLeft size={16} />
            <span>{t("header.back", "返回")}</span>
          </button>

          <div className="hidden h-7 w-px bg-[hsl(var(--separator-color))] sm:block" />

          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[hsl(var(--accent-primary)/0.16)] ring-1 ring-[hsl(var(--accent-primary)/0.28)]">
              <Shield size={17} className="text-[hsl(var(--accent-primary))]" />
            </div>
            <h1 className="hidden text-sm font-semibold tracking-wide text-[hsl(var(--text-primary))] sm:block">
              {t("header.title", "管理后台")}
            </h1>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {user && (
          <div className="flex items-center gap-2 rounded-lg border border-[hsl(var(--separator-color))] bg-[hsl(var(--bg-tertiary)/0.28)] px-2 py-1.5">
            <span className="hidden text-sm text-[hsl(var(--text-secondary))] md:block">
              {user.username}
            </span>
            <UserAvatar
              username={user.username}
              avatarUrl={user.avatar_url}
              size={32}
            />
          </div>
        )}
      </div>
    </header>
  );
};

export default AdminHeader;

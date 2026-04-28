import React, { useState } from "react";
import { Outlet } from "react-router-dom";
import { AdminSidebar } from "./AdminSidebar";
import { AdminHeader } from "./AdminHeader";
import { useIsMobile } from "../../hooks/useMediaQuery";

export const AdminLayout: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const isMobile = useIsMobile();

  return (
    <div className="fixed inset-0 flex h-screen w-screen flex-col overflow-hidden bg-[hsl(var(--bg-primary))] text-[hsl(var(--text-primary))]">
      <AdminHeader onMenuClick={() => setSidebarOpen(!sidebarOpen)} />

      <div className="flex flex-1 overflow-hidden">
        {!isMobile ? (
          <aside className="w-64 shrink-0 overflow-y-auto border-r border-[hsl(var(--separator-color))] bg-[hsl(var(--bg-secondary)/0.7)] backdrop-blur-xl lg:w-72">
            <AdminSidebar />
          </aside>
        ) : (
          <>
            {sidebarOpen && (
              <div
                className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm md:hidden"
                onClick={() => setSidebarOpen(false)}
              />
            )}

            <div
              className={`fixed top-14 bottom-0 left-0 z-50 w-72 max-w-[88vw] border-r border-[hsl(var(--separator-color))] bg-[hsl(var(--bg-secondary))] shadow-2xl transition-transform duration-200 ease-out md:hidden ${
                sidebarOpen ? "translate-x-0" : "-translate-x-full"
              }`}
            >
              <AdminSidebar onClose={() => setSidebarOpen(false)} />
            </div>
          </>
        )}

        <main className="flex-1 overflow-y-auto bg-[radial-gradient(140%_120%_at_0%_0%,hsl(var(--bg-tertiary)/0.3),transparent_58%)]">
          <div className="mx-auto w-full max-w-[1600px] px-3 py-4 sm:px-4 md:px-6 md:py-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};

export default AdminLayout;

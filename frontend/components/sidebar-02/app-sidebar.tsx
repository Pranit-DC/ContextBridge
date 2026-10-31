"use client";

import { motion, useReducedMotion } from "framer-motion";
import { useEffect, type ReactNode } from "react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";
import { Logo } from "@/components/sidebar-02/logo";
import type { Route } from "@/components/sidebar-02/nav-main";
import DashboardNavigation from "@/components/sidebar-02/nav-main";
export function DashboardSidebar({
  routes,
  active,
  onNavigate,
  projectControl,
  footer,
}: {
  routes: Route[];
  active: string;
  onNavigate: (id: string) => void;
  projectControl: ReactNode;
  footer: ReactNode;
}) {
  const { state, isMobile, setOpenMobile } = useSidebar();
  useEffect(() => {
    setOpenMobile(false);
  }, [active, setOpenMobile]);
  const reduceMotion = useReducedMotion();
  const isCollapsed = !isMobile && state === "collapsed";

  return (
    <Sidebar
      collapsible="icon"
      variant="inset"
      role="complementary"
      aria-label="Workspace navigation"
    >
      <SidebarHeader
        className={cn(
          "flex md:pt-3.5",
          isCollapsed
            ? "flex-row items-center justify-between gap-y-4 md:flex-col md:items-start md:justify-start"
            : "flex-row items-center justify-between",
        )}
      >
        <button
          type="button"
          aria-label="ContextBridge overview"
          className="flex items-center gap-2 text-left"
          onClick={() => {
            onNavigate("Overview");
            setOpenMobile(false);
          }}
        >
          <Logo className="h-8 w-8" />
          {!isCollapsed && (
            <span className="font-semibold text-foreground">ContextBridge</span>
          )}
        </button>

        <motion.div
          animate={{ opacity: 1 }}
          className={cn(
            "flex items-center gap-2",
            isCollapsed ? "flex-row md:flex-col-reverse" : "flex-row",
          )}
          initial={false}
          key={isCollapsed ? "header-collapsed" : "header-expanded"}
          transition={{ duration: reduceMotion ? 0 : 0.15 }}
        >
          <SidebarTrigger />
        </motion.div>
      </SidebarHeader>
      <SidebarContent className="gap-6 px-3 py-4">
        {!isCollapsed && (
          <div className="sidebar-project">{projectControl}</div>
        )}
        <nav aria-label="Main navigation">
          <DashboardNavigation
            routes={routes}
            active={active}
            onNavigate={onNavigate}
          />
        </nav>
      </SidebarContent>
      <SidebarFooter className="border-t border-sidebar-border px-3 py-3">
        {footer}
      </SidebarFooter>
    </Sidebar>
  );
}

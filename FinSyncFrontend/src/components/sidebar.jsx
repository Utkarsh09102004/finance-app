"use client";
import React, { useState } from "react";
import {
  ChevronRight,
  Settings,
  CreditCard,
  LogOut,
  User,
  Menu,
  Building2,
  UserCog,
  SlidersHorizontal,
  PlusCircle,
  Loader2,
} from "lucide-react";
import { Button } from "./ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "./ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuGroup,
} from "./ui/dropdown-menu";
import { cn } from "../lib/utils";
import { useWindowWidth } from "@react-hook/window-size";
import { ScrollArea } from "./ui/scroll-area";
import { Separator } from "./ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "./ui/tooltip";
import { useNavigate } from 'react-router-dom';

const menuItems = [
  {
    label: "Organisation Setting",
    icon: Building2,
    href: "/organizations",
  },
  {
    label: "Account Setting",
    icon: UserCog,
    href: "/dashboard/account-settings",
  },
  {
    label: "Preferences",
    icon: SlidersHorizontal,
    href: "/dashboard/preferences",
  },
];

export function Sidebar({
  isCollapsed: initialIsCollapsed = false,
  onCollapseChange,
  bgColor,
  conversations = [],
  onSelectConversation,
  activeConversationId,
  onNewChat,
  conversationsLoading = false,
}) {
  const [isCollapsed, setIsCollapsed] = useState(initialIsCollapsed);
  const onlyWidth = useWindowWidth();
  const mobileWidth = onlyWidth < 768;
  const navigate = useNavigate();

  const toggleSidebar = () => {
    const newCollapsedState = !isCollapsed;
    setIsCollapsed(newCollapsedState);
    onCollapseChange?.(newCollapsedState);
  };

  const handleNavigate = (href) => {
    navigate(href);
    if (mobileWidth) {
      setIsCollapsed(true);
      onCollapseChange?.(true);
    }
  };

  const handleNewChat = () => {
    onNewChat?.();
    if (mobileWidth) {
      setIsCollapsed(true);
      onCollapseChange?.(true);
    }
  };

  const handleConversationClick = (conversationId) => {
    if (!conversationId) return;
    onSelectConversation?.(conversationId);
    if (mobileWidth) {
      setIsCollapsed(true);
      onCollapseChange?.(true);
    }
  };

  const formatRelativeTime = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) return '';
    const diff = Date.now() - date.getTime();
    const minute = 60 * 1000;
    const hour = minute * 60;
    const day = hour * 24;

    if (diff < minute) return 'Just now';
    if (diff < hour) return `${Math.floor(diff / minute)}m ago`;
    if (diff < day) return `${Math.floor(diff / hour)}h ago`;
    if (diff < day * 7) return `${Math.floor(diff / day)}d ago`;
    return date.toLocaleDateString();
  };

  const renderConversationList = () => {
    if (conversationsLoading) {
      return (
        <div className="flex items-center justify-center py-4 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin mr-2" /> Loading chats...
        </div>
      );
    }

    if (!conversations.length) {
      return (
        <p className="text-sm text-muted-foreground">
          {isCollapsed ? 'No chats' : 'No conversations yet'}
        </p>
      );
    }

    return conversations.map((conversation) => {
      const isActive = conversation.id === activeConversationId;
      const title = conversation.title || 'New Conversation';
      const latestActivity = formatRelativeTime(conversation.updated_at);

      if (isCollapsed) {
        return (
          <Tooltip key={conversation.id} delayDuration={0}>
            <TooltipTrigger asChild>
              <button
                onClick={() => handleConversationClick(conversation.id)}
                className={cn(
                  'h-9 w-full rounded-full border text-sm font-medium transition',
                  isActive
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border text-foreground/70 hover:bg-muted/70'
                )}
              >
                {title.charAt(0).toUpperCase()}
              </button>
            </TooltipTrigger>
            <TooltipContent side="right" className="max-w-xs">
              <div className="flex flex-col gap-1">
                <span className="font-medium">{title}</span>
                <span className="text-xs text-muted-foreground">Last active {latestActivity}</span>
              </div>
            </TooltipContent>
          </Tooltip>
        );
      }

      return (
        <div
          key={conversation.id}
          onClick={() => handleConversationClick(conversation.id)}
          className={cn(
            'group w-full cursor-pointer rounded-lg px-3 py-2 transition hover:bg-muted/60',
            isActive && 'bg-primary/5'
          )}
        >
          <div className="flex items-center gap-3">
            <div className="flex flex-col gap-0.5">
              <span className="text-sm font-medium text-foreground truncate">{title}</span>
              <span className="text-xs text-muted-foreground">Last active {latestActivity}</span>
            </div>
          </div>
        </div>
      );
    });
  };

  return (
    <TooltipProvider>
      <div
        className={cn(
          "fixed left-0 top-0 z-50 flex h-full flex-col border-r transition-all duration-300 ease-in-out",
          bgColor ? '' : 'bg-background',
          mobileWidth ? "w-full" : isCollapsed ? "w-[70px]" : "w-64",
          mobileWidth && isCollapsed && "hidden"
        )}
        style={bgColor ? { backgroundColor: bgColor } : {}}
      >
        {mobileWidth && !isCollapsed && (
          <div className="flex items-center justify-between p-4 border-b">
            <div className="flex items-center gap-2">
              <img src="/logo.svg" alt="FinSync Logo" className="h-8 w-8" />
              <span className="font-semibold">FinSync</span>
            </div>
            <Button variant="ghost" size="icon" onClick={toggleSidebar}>
              <Menu className="h-6 w-6" />
            </Button>
          </div>
        )}

        {!mobileWidth && (
          <div
            className={cn(
              "flex h-[60px] items-center border-b",
              isCollapsed ? "justify-center" : "justify-between px-6"
            )}
          >
            {!isCollapsed && (
              <div className="flex items-center gap-2">
                <img src="/logo.svg" alt="FinSync Logo" className="h-8 w-8" />
                <span className="font-semibold">FinSync</span>
              </div>
            )}
            <Button variant="ghost" size="icon" onClick={toggleSidebar} className={cn(isCollapsed && "mx-auto")}
            >
              <ChevronRight
                className={cn(
                  "h-5 w-5 transition-transform duration-300",
                  !isCollapsed && "rotate-180"
                )}
              />
            </Button>
          </div>
        )}

        <div className={cn("px-4 pt-5 pb-2", isCollapsed && "flex justify-center")}
        >
          <Button
            className={cn(
              "py-6 rounded-full shadow-sm bg-gray-500/10 hover:bg-gray-500/15 text-foreground flex items-center justify-center",
              isCollapsed ? "w-14 h-14 p-0" : "w-[80%] mx-auto gap-2"
            )}
            onClick={handleNewChat}
          >
            <PlusCircle className="h-6 w-6" />
            {!isCollapsed && <span className="font-medium">New Chat</span>}
          </Button>
        </div>

        <ScrollArea className="flex-grow">
          <nav className="mt-4 space-y-2 px-4 pb-6">
            {menuItems.map((item) => (
              <Tooltip key={item.label} delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    className={cn(
                      "w-full justify-start gap-3 rounded-md px-3 py-3 text-sm font-medium hover:bg-muted",
                      isCollapsed && "justify-center"
                    )}
                    onClick={() => handleNavigate(item.href)}
                  >
                    <item.icon className={cn("h-5 w-5", isCollapsed && "mx-auto")} />
                    {!isCollapsed && item.label}
                  </Button>
                </TooltipTrigger>
                {isCollapsed && (
                  <TooltipContent side="right" className="flex items-center gap-4">
                    {item.label}
                  </TooltipContent>
                )}
              </Tooltip>
            ))}
          </nav>

          <div className="px-4 pb-6">
            {!isCollapsed && (
              <p className="text-xs uppercase tracking-wide text-muted-foreground mb-3">
                Recent Conversations
              </p>
            )}
            <div className="space-y-2">
              {renderConversationList()}
            </div>
          </div>
        </ScrollArea>

        <Separator className={cn("mb-3", isCollapsed ? "w-10/12 mx-auto" : "mx-1")} />

        <div className={cn("p-4", isCollapsed && "py-4")}
        >
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                className={cn(
                  "w-full justify-start gap-3 rounded-md px-3 py-3 text-sm font-medium hover:bg-muted",
                  isCollapsed && "justify-center"
                )}
              >
                {isCollapsed ? (
                  <Avatar className="h-8 w-8">
                    <AvatarImage src="https://github.com/shadcn.png" alt="@shadcn" />
                    <AvatarFallback>CN</AvatarFallback>
                  </Avatar>
                ) : (
                  <>
                    <Avatar className="h-9 w-9">
                      <AvatarImage src="https://github.com/shadcn.png" alt="@shadcn" />
                      <AvatarFallback>CN</AvatarFallback>
                    </Avatar>
                    <div className="flex flex-col items-start">
                      <span className="text-sm font-medium">shadcn</span>
                      <span className="text-xs text-muted-foreground">m@example.com</span>
                    </div>
                  </>
                )}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent sideOffset={8} align="start" className={cn("w-[200px]", isCollapsed ? "ml-2" : "")}
            >
              <DropdownMenuLabel>My Account</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuGroup>
                <DropdownMenuItem className="gap-2">
                  <User className="h-4 w-4" /> Profile
                </DropdownMenuItem>
                <DropdownMenuItem className="gap-2">
                  <CreditCard className="h-4 w-4" /> Billing
                </DropdownMenuItem>
                <DropdownMenuItem className="gap-2">
                  <Settings className="h-4 w-4" /> Settings
                </DropdownMenuItem>
              </DropdownMenuGroup>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="gap-2" onClick={() => navigate('/login')}>
                <LogOut className="h-4 w-4" /> Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      {mobileWidth && !isCollapsed && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:hidden"
          onClick={toggleSidebar}
        ></div>
      )}
    </TooltipProvider>
  );
}

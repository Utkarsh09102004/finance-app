"use client";
import React, { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  LayoutGrid,
  Settings,
  ShoppingCart,
  Users,
  Wallet,
  BarChartBig,
  CreditCard,
  Landmark,
  LogOut,
  User,
  Menu, // Added Menu icon for mobile toggle
  Building2,       // For Organisation Setting
  UserCog,         // For Account Setting
  SlidersHorizontal, // For Preferences
  History,         // For History
  MessageSquare,   // For Chat items
  PlusCircle,      // For New Chat button
} from "lucide-react";
import { Button } from "./ui/button"; // Assuming button.jsx is in ui folder
import { Avatar, AvatarFallback, AvatarImage } from "./ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuGroup,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuPortal,
} from "./ui/dropdown-menu";
import { cn } from "../lib/utils"; // Adjusted path
import { useWindowWidth } from "@react-hook/window-size";
import { ScrollArea } from "./ui/scroll-area"; // Assuming scroll-area.jsx is in ui folder
import { Separator } from "./ui/separator"; // Assuming separator.jsx is in ui folder
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "./ui/tooltip"; // Assuming tooltip.jsx is in ui folder
import { useNavigate } from 'react-router-dom';


const menuItems = [
  {
    label: "Organisation Setting",
    icon: Building2,
    href: "/organizations", // Updated to point to our Organizations page
  },
  {
    label: "Account Setting",
    icon: UserCog,
    href: "/dashboard/account-settings", // Example path
  },
  {
    label: "Preferences",
    icon: SlidersHorizontal,
    href: "/dashboard/preferences", // Example path
  },
  // Placeholder for Separator, will be handled in JSX
  {
    label: "History",
    icon: History,
    href: "/dashboard/history", // Main link for history if needed, or just a toggle
    submenu: [
      {
        label: "Chat 1",
        icon: MessageSquare,
        href: "/dashboard/history/chat/1", // Example path
      },
      {
        label: "Chat 2",
        icon: MessageSquare,
        href: "/dashboard/history/chat/2", // Example path
      },
      {
        label: "Chat 3",
        icon: MessageSquare,
        href: "/dashboard/history/chat/3", // Example path
      },
    ],
  },
  // Removed old items: Transactions, Accounts, Budgets, Customers, Settings (general)
  // Settings might be part of Account Setting or Preferences now
];

export function Sidebar({ isCollapsed: initialIsCollapsed = false, onCollapseChange, bgColor }) {
  const [isCollapsed, setIsCollapsed] = useState(initialIsCollapsed);
  const [openSubmenus, setOpenSubmenus] = useState({});
  const onlyWidth = useWindowWidth();
  const mobileWidth = onlyWidth < 768;
  const navigate = useNavigate();

  const toggleSidebar = () => {
    const newCollapsedState = !isCollapsed;
    setIsCollapsed(newCollapsedState);
    if (onCollapseChange) {
        onCollapseChange(newCollapsedState);
    }
  };

  const toggleSubmenu = (label) => {
    setOpenSubmenus((prev) => ({
      ...prev,
      [label]: !prev[label],
    }));
  };

  const handleNavigate = (href) => {
    navigate(href);
    if (mobileWidth) {
      // Close sidebar on navigation in mobile view
      const newCollapsedState = true;
      setIsCollapsed(newCollapsedState);
      if (onCollapseChange) {
          onCollapseChange(newCollapsedState);
      }
    }
  };
  
  // Update isCollapsed state when initialIsCollapsed prop changes (for mobile view)
  React.useEffect(() => {
    if (mobileWidth) {
        setIsCollapsed(true);
        if (onCollapseChange) {
            onCollapseChange(true);
        }
    } else {
        setIsCollapsed(initialIsCollapsed);
         if (onCollapseChange) {
            onCollapseChange(initialIsCollapsed);
        }
    }
  }, [mobileWidth, initialIsCollapsed, onCollapseChange]);


  return (
    <TooltipProvider>
      <div
        className={cn(
          "fixed left-0 top-0 z-50 flex h-full flex-col border-r transition-all duration-300 ease-in-out",
          bgColor ? '' : 'bg-background',
          mobileWidth ? "w-full" : (isCollapsed ? "w-[70px]" : "w-64"),
          mobileWidth && isCollapsed && "hidden" // Hide sidebar completely in mobile when collapsed
        )}
        style={bgColor ? { backgroundColor: bgColor } : {}}
      >
        {/* Mobile Header */}
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

        {/* Desktop Header / Collapsed view icon */}
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
                <Button variant="ghost" size="icon" onClick={toggleSidebar} className={cn(isCollapsed && "mx-auto")}>
                    <ChevronRight
                        className={cn(
                        "h-5 w-5 transition-transform duration-300",
                        !isCollapsed && "rotate-180"
                        )}
                    />
                </Button>
            </div>
        )}

        {/* New Chat Button */}
        <div className={cn("px-4 pt-5 pb-2", isCollapsed && "flex justify-center")}>
            <Button 
                className={cn(
                    "py-6 rounded-full shadow-sm bg-gray-500/10 hover:bg-gray-500/15 text-foreground flex items-center justify-center",
                    isCollapsed ? "w-14 h-14 p-0" : "w-[80%] mx-auto gap-2"
                )}
                onClick={() => handleNavigate('/dashboard/new-chat')}
            >
                <PlusCircle className="h-6 w-6" />
                {!isCollapsed && <span className="font-medium">New Chat</span>}
            </Button>
        </div>

        <ScrollArea className="flex-grow">
          <nav className="mt-4 space-y-2 px-4 pb-6">
            {menuItems.slice(0, 3).map((item) => ( // Top 3 items: Org Setting, Account Setting, Preferences
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

            <Separator className={cn("my-4", isCollapsed ? "w-10/12 mx-auto" : "mx-1")} />

            {menuItems.slice(3).map((item) => // History item and any subsequent items
              item.submenu ? (
                <div key={item.label}>
                  <Button
                    variant="ghost"
                    className={cn(
                      "w-full justify-between gap-3 rounded-md px-3 py-3 text-sm font-medium hover:bg-muted",
                      isCollapsed && "justify-center"
                    )}
                    onClick={() => toggleSubmenu(item.label)}
                  >
                    <div className="flex items-center gap-3">
                      <item.icon className={cn("h-5 w-5", isCollapsed && "mx-auto")} />
                      {!isCollapsed && <span>{item.label}</span>}
                    </div>
                    {!isCollapsed && (
                      openSubmenus[item.label] ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )
                    )}
                  </Button>
                  {!isCollapsed && openSubmenus[item.label] && (
                    <div className="ml-6 mt-2 space-y-2 border-l border-dashed pl-4">
                      {item.submenu.map((subItem) => (
                        <Button
                          key={subItem.label}
                          variant="ghost"
                          className="w-full justify-start gap-3 rounded-md px-3 py-2 text-sm font-medium hover:bg-muted"
                          onClick={() => handleNavigate(subItem.href)}
                        >
                          <subItem.icon className="h-5 w-5" />
                          {subItem.label}
                        </Button>
                      ))}
                    </div>
                  )}
                  {isCollapsed && (
                     <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                             <Button
                                variant="ghost"
                                className="w-full justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium hover:bg-muted"
                            >
                                <item.icon className="h-5 w-5 mx-auto" />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent side="right" align="start" sideOffset={8}>
                            <DropdownMenuLabel>{item.label}</DropdownMenuLabel>
                            <DropdownMenuSeparator />
                            {item.submenu.map((subItem) => (
                                <DropdownMenuItem key={subItem.label} onClick={() => handleNavigate(subItem.href)} className="gap-2">
                                    <subItem.icon className="h-5 w-5" />
                                    {subItem.label}
                                </DropdownMenuItem>
                            ))}
                        </DropdownMenuContent>
                    </DropdownMenu>
                  )}
                </div>
              ) : (
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
              )
            )}
          </nav>
        </ScrollArea>

        <div className="mt-auto"></div>
        <Separator className={cn("mb-3", isCollapsed ? "w-10/12 mx-auto" : "mx-1")} />

        <div className={cn("p-4", isCollapsed && "py-4")}>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className={cn("w-full justify-start gap-3 rounded-md px-3 py-3 text-sm font-medium hover:bg-muted", isCollapsed && "justify-center")}>
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
                      <span className="text-xs text-muted-foreground">
                        m@example.com
                      </span>
                    </div>
                  </>
                )}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent sideOffset={8} align="start" className={cn("w-[200px]", isCollapsed ? "ml-2" : "")}>
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
      {/* Mobile Overlay - shown when sidebar is open */}
      {mobileWidth && !isCollapsed && (
          <div 
              className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:hidden"
              onClick={toggleSidebar}
          ></div>
      )}
    </TooltipProvider>
  );
} 
"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Zap, LayoutDashboard, Store, LogOut, Play } from "lucide-react";
import StatusBadge from "./StatusBadge";
import type { AuthState } from "@/lib/types";

export default function Navbar() {
    const pathname = usePathname();
    const router = useRouter();
    const [auth, setAuth] = useState<AuthState | null>(null);

    useEffect(() => {
        const raw = localStorage.getItem("acf_auth");
        if (raw) {
            try {
                setAuth(JSON.parse(raw));
            } catch {
                /* ignore */
            }
        }
    }, []);

    const handleLogout = () => {
        localStorage.removeItem("acf_auth");
        router.push("/");
    };

    const navLinks = [
        { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
        { href: "/marketplace", label: "Marketplace", icon: Store },
        { href: "/demo", label: "Live Demo", icon: Play },
    ];

    return (
        <nav className="sticky top-0 z-50 border-b border-[#2a2a3d] bg-[#0a0a0f]/80 backdrop-blur-xl">
            <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
                {/* Left: Logo + nav links */}
                <div className="flex items-center gap-8">
                    <Link
                        href="/"
                        className="flex items-center gap-2 text-lg font-bold tracking-tight text-white transition-colors hover:text-indigo-400"
                    >
                        <Zap className="h-5 w-5 text-indigo-400" />
                        <span>ACF</span>
                    </Link>

                    {auth && (
                        <div className="flex items-center gap-1">
                            {navLinks.map(({ href, label, icon: Icon }) => (
                                <Link
                                    key={href}
                                    href={href}
                                    className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${pathname === href
                                            ? "bg-white/10 text-white"
                                            : "text-gray-400 hover:bg-white/5 hover:text-white"
                                        }`}
                                >
                                    <Icon className="h-4 w-4" />
                                    {label}
                                </Link>
                            ))}
                        </div>
                    )}
                </div>

                {/* Right: user info */}
                {auth && (
                    <div className="flex items-center gap-4">
                        <div className="flex items-center gap-3">
                            <span className="relative flex h-2.5 w-2.5">
                                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
                                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-400" />
                            </span>
                            <span className="text-sm font-medium text-gray-200">
                                {auth.legal_name}
                            </span>
                            <StatusBadge status={auth.role} size="sm" pulse={false} />
                        </div>
                        <button
                            onClick={handleLogout}
                            className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-white/10 hover:text-white"
                            title="Logout"
                        >
                            <LogOut className="h-4 w-4" />
                        </button>
                    </div>
                )}
            </div>
        </nav>
    );
}

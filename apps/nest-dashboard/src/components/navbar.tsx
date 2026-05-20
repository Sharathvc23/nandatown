"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Home" },
  { href: "/agents", label: "Agents" },
  { href: "/leaderboard", label: "Leaderboard" },
  { href: "/experiments", label: "Experiments" },
  { href: "/visualizer", label: "Visualizer" },
  { href: "/docs", label: "Docs" },
];

export function Navbar() {
  const pathname = usePathname();

  return (
    <nav className="sticky top-0 z-50 border-b border-warm-200 bg-white/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-3 group">
          <Image
            src="/logo.svg"
            alt="NEST logo"
            width={32}
            height={32}
            className="rounded-md"
          />
          <span className="text-lg font-semibold tracking-tight text-warm-900">
            NEST
          </span>
          <span className="hidden sm:flex items-center gap-2 pl-3 ml-1 border-l border-warm-200 text-xs text-warm-400">
            <Image
              src="/brand/nanda-logo-color.png"
              alt="Project NANDA"
              width={18}
              height={18}
              className="rounded-sm opacity-90 group-hover:opacity-100 transition-opacity"
            />
            <span className="uppercase tracking-widest font-medium">
              Project NANDA
            </span>
          </span>
        </Link>

        <div className="hidden items-center gap-1 md:flex">
          {links.map((link) => {
            const isActive =
              link.href === "/"
                ? pathname === "/"
                : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`rounded-lg px-3.5 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-warm-100 text-warm-900"
                    : "text-warm-500 hover:text-warm-900 hover:bg-warm-50"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </div>

        <a
          href="https://github.com/mariagorskikh/nest"
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-lg border border-warm-200 px-4 py-2 text-sm font-medium text-warm-700 transition-colors hover:bg-warm-50"
        >
          GitHub
        </a>
      </div>
    </nav>
  );
}

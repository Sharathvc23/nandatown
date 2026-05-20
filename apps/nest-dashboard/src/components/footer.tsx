import Image from "next/image";
import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-warm-200 bg-white">
      <div className="mx-auto max-w-7xl px-6 py-16">
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
          <div className="col-span-2 md:col-span-1">
            <div className="flex items-center gap-3">
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
            </div>
            <p className="mt-4 text-sm leading-6 text-warm-500">
              Network Environment for Swarm Testing &mdash; a discrete-event
              testbed for multi-agent protocols.
            </p>
            <a
              href="https://projectnanda.org"
              target="_blank"
              rel="noopener noreferrer"
              className="mt-5 inline-flex items-center gap-2 text-xs text-warm-500 hover:text-warm-900 transition-colors"
            >
              <Image
                src="/brand/nanda-logo-color.png"
                alt="Project NANDA"
                width={16}
                height={16}
                className="rounded-sm"
              />
              <span className="uppercase tracking-widest font-medium">
                Part of Project NANDA
              </span>
            </a>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-warm-900">Platform</h3>
            <ul className="mt-4 space-y-3">
              <li>
                <Link href="/experiments" className="text-sm text-warm-500 hover:text-warm-900 transition-colors">
                  Experiments
                </Link>
              </li>
              <li>
                <Link href="/leaderboard" className="text-sm text-warm-500 hover:text-warm-900 transition-colors">
                  Leaderboard
                </Link>
              </li>
              <li>
                <Link href="/visualizer" className="text-sm text-warm-500 hover:text-warm-900 transition-colors">
                  Visualizer
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-warm-900">Resources</h3>
            <ul className="mt-4 space-y-3">
              <li>
                <Link href="/docs" className="text-sm text-warm-500 hover:text-warm-900 transition-colors">
                  Documentation
                </Link>
              </li>
              <li>
                <a
                  href="https://github.com/mariagorskikh/nest"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-warm-500 hover:text-warm-900 transition-colors"
                >
                  GitHub
                </a>
              </li>
              <li>
                <a
                  href="https://projectnanda.org"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-warm-500 hover:text-warm-900 transition-colors"
                >
                  Project NANDA
                </a>
              </li>
            </ul>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-warm-900">Community</h3>
            <ul className="mt-4 space-y-3">
              <li>
                <a
                  href="https://github.com/mariagorskikh/nest/issues"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-warm-500 hover:text-warm-900 transition-colors"
                >
                  Report a Bug
                </a>
              </li>
              <li>
                <a
                  href="https://github.com/mariagorskikh/nest/discussions"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-warm-500 hover:text-warm-900 transition-colors"
                >
                  Discussions
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-12 border-t border-warm-200 pt-8">
          <p className="text-sm text-warm-400">
            &copy; {new Date().getFullYear()} NEST &mdash; Apache 2.0 License.
            Built at MIT Media Lab.
          </p>
        </div>
      </div>
    </footer>
  );
}

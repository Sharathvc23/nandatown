"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  geoNaturalEarth1,
  geoPath,
  type GeoPermissibleObjects,
  type GeoProjection,
} from "d3-geo";
import { feature } from "topojson-client";
import type {
  Topology,
  GeometryCollection,
  GeometryObject,
} from "topojson-specification";
import type { Feature, FeatureCollection } from "geojson";
import {
  clusters,
  clusterLinks,
  jitterAgents,
  totalAgents,
  type AgentCluster,
  type MessageLink,
} from "@/lib/agent-network";

/* ---------------------------------------------------------------- */
/*  Layout constants                                                 */
/* ---------------------------------------------------------------- */

const WIDTH = 1100;
const HEIGHT = 560;

/* ---------------------------------------------------------------- */
/*  World map hook                                                   */
/* ---------------------------------------------------------------- */

interface WorldData {
  countries: FeatureCollection;
  projection: GeoProjection;
  path: (g: GeoPermissibleObjects) => string;
}

function useWorldMap(): WorldData | null {
  const [data, setData] = useState<WorldData | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/world-110m.json")
      .then((r) => r.json() as Promise<Topology>)
      .then((topo) => {
        if (cancelled) return;
        const countries = feature(
          topo,
          topo.objects.countries as GeometryCollection<GeometryObject>,
        ) as unknown as FeatureCollection;

        // Natural Earth projection — a calm, academic look, similar to
        // the maps you see in scientific publications.
        const projection = geoNaturalEarth1()
          .scale(195)
          .translate([WIDTH / 2, HEIGHT / 2 + 10]);

        const path = geoPath(projection) as unknown as (
          g: GeoPermissibleObjects,
        ) => string;

        setData({ countries, projection, path });
      })
      .catch(() => {
        /* ignore — page renders without the map background if the fetch fails */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return data;
}

/* ---------------------------------------------------------------- */
/*  Animated message lines                                           */
/* ---------------------------------------------------------------- */

interface ActiveMessage {
  id: number;
  link: MessageLink;
  bornAt: number;
}

function useMessageStream(intervalMs = 650, lifetimeMs = 2400) {
  const [messages, setMessages] = useState<ActiveMessage[]>([]);
  const idRef = useRef(0);

  useEffect(() => {
    const tick = setInterval(() => {
      const now = performance.now();
      idRef.current += 1;
      const link =
        clusterLinks[Math.floor(Math.random() * clusterLinks.length)];
      setMessages((prev) =>
        // Drop expired, then append the new one.
        [
          ...prev.filter((m) => now - m.bornAt < lifetimeMs),
          { id: idRef.current, link, bornAt: now },
        ].slice(-18),
      );
    }, intervalMs);

    // Also a slower "garbage-collect" pass so the list shrinks even
    // when intervals are dropped while the tab is backgrounded.
    const sweep = setInterval(() => {
      const now = performance.now();
      setMessages((prev) => prev.filter((m) => now - m.bornAt < lifetimeMs));
    }, 1000);

    return () => {
      clearInterval(tick);
      clearInterval(sweep);
    };
  }, [intervalMs, lifetimeMs]);

  return messages;
}

/* ---------------------------------------------------------------- */
/*  Stats bar                                                        */
/* ---------------------------------------------------------------- */

function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="flex flex-col">
      <span className="text-[11px] font-mono uppercase tracking-widest text-warm-400">
        {label}
      </span>
      <span className="mt-1 text-2xl font-medium text-warm-900 tabular-nums">
        {value}
      </span>
      {hint && (
        <span className="mt-1 text-xs text-warm-500">{hint}</span>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- */
/*  Map                                                              */
/* ---------------------------------------------------------------- */

function AgentMap({
  world,
  hovered,
  setHovered,
}: {
  world: WorldData | null;
  hovered: string | null;
  setHovered: (city: string | null) => void;
}) {
  const projectedClusters = useMemo(() => {
    if (!world) return [];
    return clusters
      .map((c) => {
        const p = world.projection(c.coords);
        return p ? { ...c, x: p[0], y: p[1] } : null;
      })
      .filter((c): c is AgentCluster & { x: number; y: number } => c !== null);
  }, [world]);

  const projectedAgents = useMemo(() => {
    if (!world) return [];
    return clusters.flatMap((c) => {
      const agents = jitterAgents(c);
      return agents.map((a) => {
        const p = world.projection(a.coords);
        return p ? { ...a, x: p[0], y: p[1] } : null;
      });
    }).filter((a): a is { id: string; cluster: string; x: number; y: number; coords: [number, number] } => a !== null);
  }, [world]);

  const messages = useMessageStream();

  // Pre-compute screen positions for active links once per render.
  const projectedMessages = useMemo(() => {
    if (!world) return [];
    const now = performance.now();
    return messages
      .map((m) => {
        const a = world.projection(m.link.from);
        const b = world.projection(m.link.to);
        if (!a || !b) return null;
        const age = now - m.bornAt;
        return {
          id: m.id,
          fromCity: m.link.fromCity,
          toCity: m.link.toCity,
          x1: a[0],
          y1: a[1],
          x2: b[0],
          y2: b[1],
          age,
        };
      })
      .filter(
        (m): m is NonNullable<typeof m> => m !== null,
      );
  }, [messages, world]);

  return (
    <div className="rounded-2xl border border-warm-200 bg-white p-4 shadow-[0_1px_0_rgba(28,25,23,0.02)]">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="block w-full h-auto"
        style={{ overflow: "visible" }}
      >
        <defs>
          {/* Soft glow for active agent dots */}
          <filter id="agent-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="1.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          {/* Gradient used to draw the moving message head */}
          <radialGradient id="msg-head" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#8B0000" stopOpacity="0.95" />
            <stop offset="60%" stopColor="#8B0000" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#8B0000" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Graticule-style horizontal bands for an academic look */}
        {Array.from({ length: 5 }, (_, i) => (
          <line
            key={`hb-${i}`}
            x1={0}
            x2={WIDTH}
            y1={(HEIGHT / 5) * (i + 1) - 30}
            y2={(HEIGHT / 5) * (i + 1) - 30}
            stroke="#F5F5F4"
            strokeWidth={1}
          />
        ))}

        {/* Countries */}
        {world &&
          world.countries.features.map((f: Feature, i: number) => (
            <path
              key={`country-${i}`}
              d={world.path(f) || ""}
              fill="#F5F5F4"
              stroke="#E7E5E4"
              strokeWidth={0.6}
            />
          ))}

        {/* Loading shimmer for the map */}
        {!world && (
          <text
            x={WIDTH / 2}
            y={HEIGHT / 2}
            textAnchor="middle"
            fontSize={13}
            fill="#A8A29E"
            fontFamily="var(--font-mono)"
          >
            Loading map…
          </text>
        )}

        {/* Animated message edges */}
        {projectedMessages.map((m) => {
          // Each line draws over ~1.2s and then fades.
          const drawDur = 1200;
          const t = Math.min(1, m.age / drawDur);
          const ease = 1 - Math.pow(1 - t, 3);
          const hx = m.x1 + (m.x2 - m.x1) * ease;
          const hy = m.y1 + (m.y2 - m.y1) * ease;
          // Fade tail in [drawDur, drawDur + 1200]
          const fade =
            m.age <= drawDur
              ? 1
              : Math.max(0, 1 - (m.age - drawDur) / 1200);

          return (
            <g key={`msg-${m.id}`} opacity={fade}>
              <line
                x1={m.x1}
                y1={m.y1}
                x2={hx}
                y2={hy}
                stroke="#8B0000"
                strokeWidth={0.9}
                strokeOpacity={0.45}
                strokeLinecap="round"
              />
              {/* Glowing head dot at the tip */}
              <circle
                cx={hx}
                cy={hy}
                r={3}
                fill="url(#msg-head)"
              />
            </g>
          );
        })}

        {/* Agent dots */}
        {projectedAgents.map((a) => {
          const isHot = hovered === a.cluster;
          return (
            <circle
              key={a.id}
              cx={a.x}
              cy={a.y}
              r={isHot ? 2.4 : 1.6}
              fill={isHot ? "#8B0000" : "#1C1917"}
              opacity={isHot ? 1 : 0.55}
              style={{ transition: "all 0.25s ease" }}
            />
          );
        })}

        {/* Cluster centroids + labels */}
        {projectedClusters.map((c) => {
          const isHot = hovered === c.city;
          return (
            <g
              key={c.city}
              onMouseEnter={() => setHovered(c.city)}
              onMouseLeave={() => setHovered(null)}
              style={{ cursor: "pointer" }}
            >
              {/* Outer pulse ring */}
              <circle
                cx={c.x}
                cy={c.y}
                r={isHot ? 16 : 10}
                fill="#8B0000"
                opacity={isHot ? 0.12 : 0.06}
                style={{ transition: "all 0.25s ease" }}
              />
              {/* Inner solid */}
              <circle
                cx={c.x}
                cy={c.y}
                r={isHot ? 4.5 : 3.5}
                fill="#8B0000"
                filter={isHot ? "url(#agent-glow)" : undefined}
                style={{ transition: "all 0.25s ease" }}
              />
              {/* City label */}
              <g style={{ pointerEvents: "none" }}>
                <text
                  x={c.x + 8}
                  y={c.y - 6}
                  fontSize={11}
                  fontFamily="var(--font-sans)"
                  fontWeight={500}
                  fill="#1C1917"
                  opacity={isHot ? 1 : 0.85}
                >
                  {c.city}
                </text>
                <text
                  x={c.x + 8}
                  y={c.y + 6}
                  fontSize={9}
                  fontFamily="var(--font-mono)"
                  fill="#78716C"
                  opacity={isHot ? 1 : 0.6}
                  letterSpacing={0.4}
                >
                  {c.region} · {c.agents}
                </text>
              </g>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/* ---------------------------------------------------------------- */
/*  Right-hand panel: legend + cluster list                          */
/* ---------------------------------------------------------------- */

function ClusterList({
  hovered,
  setHovered,
}: {
  hovered: string | null;
  setHovered: (city: string | null) => void;
}) {
  const sorted = useMemo(
    () => [...clusters].sort((a, b) => b.agents - a.agents),
    [],
  );
  return (
    <div className="rounded-2xl border border-warm-200 bg-white">
      <div className="border-b border-warm-100 px-5 py-3">
        <h3 className="text-[11px] font-mono uppercase tracking-widest text-warm-500">
          Clusters
        </h3>
      </div>
      <ul className="divide-y divide-warm-100">
        {sorted.map((c) => {
          const isHot = hovered === c.city;
          return (
            <li
              key={c.city}
              onMouseEnter={() => setHovered(c.city)}
              onMouseLeave={() => setHovered(null)}
              className={`flex items-center gap-3 px-5 py-3 transition-colors cursor-default ${
                isHot ? "bg-warm-50" : ""
              }`}
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{
                  background: isHot ? "#8B0000" : "#1C1917",
                  opacity: isHot ? 1 : 0.7,
                }}
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-warm-900 leading-tight truncate">
                  {c.city}
                  {c.affiliation && (
                    <span className="ml-2 text-xs text-warm-400 font-normal">
                      {c.affiliation}
                    </span>
                  )}
                </p>
                <p className="text-[11px] font-mono text-warm-400 mt-0.5">
                  {c.region}
                </p>
              </div>
              <span className="text-sm tabular-nums text-warm-700">
                {c.agents}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/* ---------------------------------------------------------------- */
/*  Page                                                             */
/* ---------------------------------------------------------------- */

export default function AgentsPage() {
  const world = useWorldMap();
  const [hovered, setHovered] = useState<string | null>(null);

  // A second of-render counter keeps the message stream painting smoothly.
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => (t + 1) % 1_000_000), 60);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="bg-warm-50">
      {/* Header band */}
      <section className="border-b border-warm-200 bg-white">
        <div className="mx-auto max-w-7xl px-6 pt-16 pb-10">
          <div className="flex items-center gap-2 text-[11px] font-mono uppercase tracking-widest text-warm-500">
            <span className="inline-flex h-1.5 w-1.5 rounded-full bg-crimson animate-pulse-dot" />
            Live · Testbed Network
          </div>
          <h1 className="mt-5 font-serif text-5xl leading-[1.05] tracking-tight text-warm-950 md:text-6xl">
            The agent network,
            <br />
            <span className="italic text-warm-700">in motion.</span>
          </h1>
          <p className="mt-6 max-w-2xl text-warm-500 text-lg leading-7">
            A view of agents currently running on the NEST testbed across the
            world. Each dot is an agent; each line is a message exchanged
            between clusters. The data shown here is synthetic — wired to a
            seeded layout — and updates continuously.
          </p>
        </div>
      </section>

      {/* Stats row */}
      <section className="border-b border-warm-200 bg-white">
        <div className="mx-auto max-w-7xl px-6 py-8 grid grid-cols-2 md:grid-cols-4 gap-8">
          <Stat label="Agents" value={String(totalAgents)} hint="across all clusters" />
          <Stat label="Clusters" value={String(clusters.length)} hint="major regions" />
          <Stat label="Messages / min" value="~92" hint="rolling 1-minute average" />
          <Stat label="Uptime" value="99.94 %" hint="last 30 days" />
        </div>
      </section>

      {/* Map + sidebar */}
      <section>
        <div className="mx-auto max-w-7xl px-6 py-12 grid gap-8 lg:grid-cols-[1fr_320px]">
          <AgentMap world={world} hovered={hovered} setHovered={setHovered} />
          <ClusterList hovered={hovered} setHovered={setHovered} />
        </div>
      </section>

      {/* Method note */}
      <section className="border-t border-warm-200 bg-white">
        <div className="mx-auto max-w-3xl px-6 py-16 text-warm-600 leading-7">
          <p className="text-[11px] font-mono uppercase tracking-widest text-warm-400">
            Method
          </p>
          <p className="mt-3 font-serif text-2xl leading-snug text-warm-900">
            How this map is drawn.
          </p>
          <p className="mt-5 text-sm">
            The world coastline is rendered from the public-domain
            Natural&nbsp;Earth dataset (1:110m), projected with{" "}
            <code className="font-mono text-[12px] text-warm-800">geoNaturalEarth1</code>.
            Agents are placed deterministically: each cluster centroid sits at
            its real city coordinates, and individual agent dots are
            scattered within ~1.6° using a string-seeded PRNG so the layout is
            identical on every reload.
          </p>
          <p className="mt-4 text-sm">
            Message lines are sampled uniformly from the set of ordered cluster
            pairs and drawn with a cubic ease so the head appears to travel
            along the great-circle approximation between two cities. The tail
            fades over one second. No data is fetched from the testbed yet —
            this page is a visualization stub that an{" "}
            <code className="font-mono text-[12px] text-warm-800">/api/agents</code>{" "}
            endpoint can drop into without changing the rendering layer.
          </p>
        </div>
      </section>
    </div>
  );
}

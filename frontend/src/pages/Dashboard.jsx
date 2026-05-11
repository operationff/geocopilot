import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "../hooks/useAuth";
import { useNavigate } from "react-router-dom";
import api from "../lib/api";

// ─── Utilities ────────────────────────────────────────────────────────────────

function fmtScore(score) {
  if (score === null || score === undefined) return "—";
  return `${Math.round(score * 100)}%`;
}

function scoreColor(score) {
  if (score === null || score === undefined) return "text-gray-400";
  if (score >= 0.7) return "text-green-600";
  if (score >= 0.4) return "text-yellow-500";
  return "text-red-500";
}

function scoreBg(score) {
  if (score === null || score === undefined) return "bg-gray-50";
  if (score >= 0.7) return "bg-green-50";
  if (score >= 0.4) return "bg-yellow-50";
  return "bg-red-50";
}

function fmtRelTime(dateStr) {
  if (!dateStr) return null;
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return new Date(dateStr).toLocaleDateString();
}

// ─── Shared primitives ────────────────────────────────────────────────────────

function Header({ user, onLogout }) {
  return (
    <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-brand-500 flex items-center justify-center">
          <span className="text-white text-sm font-bold">G</span>
        </div>
        <span className="font-semibold text-gray-900">GEOCopilot</span>
      </div>
      <div className="flex items-center gap-4">
        <span className="text-sm text-gray-600">{user?.email}</span>
        <button
          onClick={onLogout}
          className="text-sm text-gray-500 hover:text-gray-700 transition"
        >
          Sign out
        </button>
      </div>
    </header>
  );
}

function SectionCard({ title, children, action, lastUpdated, loading }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-gray-900">{title}</h3>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs text-gray-400">Updated {fmtRelTime(lastUpdated)}</span>
          )}
          {loading && (
            <span className="w-3 h-3 rounded-full border-2 border-brand-400 border-t-transparent animate-spin inline-block" />
          )}
          {action}
        </div>
      </div>
      {children}
    </div>
  );
}

function InputField({ label, name, value, onChange, placeholder, type = "text" }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-500 mb-1">{label}</label>
      <input
        type={type}
        name={name}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
      />
    </div>
  );
}

function ErrorMsg({ msg }) {
  if (!msg) return null;
  return <p className="text-xs text-red-500 mt-1">{msg}</p>;
}

// ─── Onboarding steps ─────────────────────────────────────────────────────────

function CreateProjectStep({ onCreated }) {
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError("");
    try {
      const { data } = await api.post("/api/projects/", { name: name.trim() });
      onCreated(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to create project");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-md mx-auto mt-16 bg-white rounded-2xl border border-gray-100 shadow-sm p-8">
      <div className="w-10 h-10 rounded-xl bg-brand-50 flex items-center justify-center mb-4">
        <span className="text-brand-500 text-lg font-bold">G</span>
      </div>
      <h2 className="text-xl font-semibold text-gray-900 mb-1">Create your first project</h2>
      <p className="text-sm text-gray-500 mb-6">
        A project groups your brand, competitors, and GEO scan results.
      </p>
      <form onSubmit={handleSubmit} className="space-y-4">
        <InputField
          label="Project name"
          name="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. My SaaS Product"
        />
        <ErrorMsg msg={error} />
        <button
          type="submit"
          disabled={loading || !name.trim()}
          className="w-full bg-brand-500 text-white rounded-lg px-4 py-2.5 text-sm font-medium hover:bg-brand-600 disabled:opacity-50 transition"
        >
          {loading ? "Creating…" : "Create project"}
        </button>
      </form>
    </div>
  );
}

function BrandSetupStep({ projectId, onComplete }) {
  const [form, setForm] = useState({
    name: "",
    website_url: "",
    description: "",
    products_services: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function handleChange(e) {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.name.trim() || !form.website_url.trim()) return;
    setLoading(true);
    setError("");
    try {
      const { data } = await api.post(`/api/projects/${projectId}/brand/`, form);
      onComplete(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to save brand");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-lg mx-auto mt-10 bg-white rounded-2xl border border-gray-100 shadow-sm p-8">
      <h2 className="text-xl font-semibold text-gray-900 mb-1">Set up your brand</h2>
      <p className="text-sm text-gray-500 mb-6">
        Tell GEOCopilot about your business so we can track how AI engines mention you.
      </p>
      <form onSubmit={handleSubmit} className="space-y-4">
        <InputField label="Business name" name="name" value={form.name} onChange={handleChange} placeholder="Acme Inc." />
        <InputField label="Website URL" name="website_url" value={form.website_url} onChange={handleChange} placeholder="https://acme.com" />
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Description</label>
          <textarea
            name="description"
            value={form.description}
            onChange={handleChange}
            placeholder="What does your business do?"
            rows={2}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">
            Products / Services <span className="text-gray-400">(optional)</span>
          </label>
          <textarea
            name="products_services"
            value={form.products_services}
            onChange={handleChange}
            placeholder="Comma-separated: CRM software, email automation, …"
            rows={2}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
          />
        </div>
        <ErrorMsg msg={error} />
        <button
          type="submit"
          disabled={loading || !form.name.trim() || !form.website_url.trim()}
          className="w-full bg-brand-500 text-white rounded-lg px-4 py-2.5 text-sm font-medium hover:bg-brand-600 disabled:opacity-50 transition"
        >
          {loading ? "Saving…" : "Save and continue"}
        </button>
      </form>
    </div>
  );
}

// ─── Brand card ───────────────────────────────────────────────────────────────

function BrandCard({ brand, projectId, onUpdated }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ ...brand });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function handleChange(e) {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));
  }

  async function handleSave(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const { data } = await api.patch(`/api/projects/${projectId}/brand/`, form);
      onUpdated(data);
      setEditing(false);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to update brand");
    } finally {
      setLoading(false);
    }
  }

  return (
    <SectionCard
      title="Brand"
      action={
        !editing && (
          <button
            onClick={() => { setForm({ ...brand }); setEditing(true); }}
            className="text-xs text-brand-500 hover:text-brand-600 font-medium"
          >
            Edit
          </button>
        )
      }
    >
      {editing ? (
        <form onSubmit={handleSave} className="space-y-3">
          <InputField label="Business name" name="name" value={form.name} onChange={handleChange} placeholder="Acme Inc." />
          <InputField label="Website URL" name="website_url" value={form.website_url} onChange={handleChange} placeholder="https://acme.com" />
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Description</label>
            <textarea
              name="description"
              value={form.description || ""}
              onChange={handleChange}
              rows={2}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Products / Services</label>
            <textarea
              name="products_services"
              value={form.products_services || ""}
              onChange={handleChange}
              rows={2}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
            />
          </div>
          <ErrorMsg msg={error} />
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={loading}
              className="bg-brand-500 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-brand-600 disabled:opacity-50 transition"
            >
              {loading ? "Saving…" : "Save"}
            </button>
            <button
              type="button"
              onClick={() => setEditing(false)}
              className="text-sm text-gray-500 hover:text-gray-700 px-4 py-2"
            >
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <div className="space-y-2">
          <div className="flex items-baseline gap-2">
            <span className="text-base font-semibold text-gray-900">{brand.name}</span>
            <a
              href={brand.website_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-brand-500 hover:underline"
            >
              {brand.website_url}
            </a>
          </div>
          {brand.description && (
            <p className="text-sm text-gray-500">{brand.description}</p>
          )}
          {brand.products_services && (
            <p className="text-xs text-gray-400">
              <span className="font-medium text-gray-500">Products/Services: </span>
              {brand.products_services}
            </p>
          )}
        </div>
      )}
    </SectionCard>
  );
}

// ─── Competitors card ─────────────────────────────────────────────────────────

function CompetitorsCard({ projectId }) {
  const [competitors, setCompetitors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ name: "", website_url: "", description: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const fetchCompetitors = useCallback(async () => {
    try {
      const { data } = await api.get(`/api/projects/${projectId}/competitors/`);
      setCompetitors(data);
    } catch {
      // silently fail on load
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { fetchCompetitors(); }, [fetchCompetitors]);

  async function handleAdd(e) {
    e.preventDefault();
    if (!form.name.trim() || !form.website_url.trim()) return;
    setSaving(true);
    setError("");
    try {
      const { data } = await api.post(`/api/projects/${projectId}/competitors/`, form);
      setCompetitors((c) => [...c, data]);
      setForm({ name: "", website_url: "", description: "" });
      setAdding(false);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to add competitor");
    } finally {
      setSaving(false);
    }
  }

  async function handleRemove(id) {
    try {
      await api.delete(`/api/projects/${projectId}/competitors/${id}`);
      setCompetitors((c) => c.filter((x) => x.id !== id));
    } catch {
      // ignore
    }
  }

  return (
    <SectionCard
      title="Competitors"
      action={
        !adding && (
          <button
            onClick={() => setAdding(true)}
            className="text-xs text-brand-500 hover:text-brand-600 font-medium"
          >
            + Add
          </button>
        )
      }
    >
      {loading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : (
        <>
          {competitors.length === 0 && !adding && (
            <p className="text-sm text-gray-400">No competitors tracked yet.</p>
          )}
          <ul className="space-y-2 mb-3">
            {competitors.map((c) => (
              <li key={c.id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                <div>
                  <span className="text-sm font-medium text-gray-800">{c.name}</span>
                  <a
                    href={c.website_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-2 text-xs text-gray-400 hover:text-brand-500"
                  >
                    {c.website_url}
                  </a>
                </div>
                <button
                  onClick={() => handleRemove(c.id)}
                  className="text-xs text-gray-400 hover:text-red-500 transition ml-4"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
          {adding && (
            <form onSubmit={handleAdd} className="space-y-2 pt-2 border-t border-gray-100">
              <div className="grid grid-cols-2 gap-2">
                <InputField
                  label="Name"
                  name="name"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="Competitor Co."
                />
                <InputField
                  label="Website"
                  name="website_url"
                  value={form.website_url}
                  onChange={(e) => setForm((f) => ({ ...f, website_url: e.target.value }))}
                  placeholder="https://competitor.com"
                />
              </div>
              <ErrorMsg msg={error} />
              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={saving || !form.name.trim() || !form.website_url.trim()}
                  className="bg-brand-500 text-white rounded-lg px-3 py-1.5 text-xs font-medium hover:bg-brand-600 disabled:opacity-50 transition"
                >
                  {saving ? "Adding…" : "Add"}
                </button>
                <button
                  type="button"
                  onClick={() => { setAdding(false); setError(""); }}
                  className="text-xs text-gray-400 hover:text-gray-600 px-3 py-1.5"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </>
      )}
    </SectionCard>
  );
}

// ─── Visibility score hero card ───────────────────────────────────────────────

const TREND_ICON = {
  up: (
    <svg className="w-5 h-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 19.5l15-15M19.5 4.5H9m10.5 0v10.5" />
    </svg>
  ),
  down: (
    <svg className="w-5 h-5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 4.5l-15 15M4.5 19.5H15M4.5 19.5V9" />
    </svg>
  ),
  stable: (
    <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14" />
    </svg>
  ),
};

function VisibilityScoreCard({ stats, loading, onRefresh }) {
  const score = stats?.overall?.current?.score ?? null;
  const trend = stats?.trend;
  const delta = stats?.overall?.trend_delta ?? null;
  const resultCount = stats?.overall?.current?.result_count ?? null;
  const citationCount = stats?.overall?.current?.citation_count ?? null;
  const computedAt = stats?.computed_at;

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
      <div className="flex items-start justify-between mb-2">
        <div>
          <h3 className="text-base font-semibold text-gray-900">Brand Visibility Score</h3>
          <p className="text-xs text-gray-400 mt-0.5">% of AI responses that mention your brand (last 7 days)</p>
        </div>
        <div className="flex items-center gap-2">
          {computedAt && (
            <span className="text-xs text-gray-400">Updated {fmtRelTime(computedAt)}</span>
          )}
          {loading && (
            <span className="w-3 h-3 rounded-full border-2 border-brand-400 border-t-transparent animate-spin inline-block" />
          )}
          <button
            onClick={onRefresh}
            disabled={loading}
            className="text-xs text-gray-400 hover:text-brand-500 transition disabled:opacity-40"
            title="Refresh"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
      </div>

      <div className="flex items-end gap-4 mt-4">
        <div className={`text-5xl font-bold ${scoreColor(score)}`}>
          {fmtScore(score)}
        </div>
        {trend && (
          <div className="flex items-center gap-1.5 mb-1">
            {TREND_ICON[trend]}
            <span className={`text-sm font-medium ${trend === "up" ? "text-green-600" : trend === "down" ? "text-red-500" : "text-gray-400"}`}>
              {delta !== null
                ? `${delta > 0 ? "+" : ""}${Math.round(delta * 100)}pp vs prior 7d`
                : trend}
            </span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-3 gap-4 mt-6 pt-4 border-t border-gray-50">
        <div>
          <p className="text-xs text-gray-400">Scans (7d)</p>
          <p className="text-lg font-semibold text-gray-800 mt-0.5">{resultCount ?? "—"}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400">Citations (7d)</p>
          <p className="text-lg font-semibold text-gray-800 mt-0.5">{citationCount ?? "—"}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400">Prior 7d score</p>
          <p className="text-lg font-semibold text-gray-800 mt-0.5">
            {stats?.overall?.previous?.score !== undefined
              ? fmtScore(stats.overall.previous.score)
              : "—"}
          </p>
        </div>
      </div>
    </div>
  );
}

// ─── Engine breakdown card ────────────────────────────────────────────────────

const ENGINE_LABELS = {
  chatgpt: "ChatGPT",
  perplexity: "Perplexity",
  gemini: "Gemini",
  google_ai_overviews: "Google AI Overviews",
};

function EngineBreakdownCard({ stats }) {
  const byEngine = stats?.by_engine ?? {};
  const entries = Object.entries(byEngine);

  return (
    <SectionCard title="By AI Engine">
      {entries.length === 0 ? (
        <p className="text-sm text-gray-400">No scan data yet.</p>
      ) : (
        <div className="space-y-3">
          {entries.map(([engine, engineStats]) => {
            const score = engineStats.current?.score ?? null;
            const pct = score !== null ? Math.round(score * 100) : null;
            const delta = engineStats.trend_delta;

            return (
              <div key={engine} className="flex items-center gap-4">
                <div className="w-36 shrink-0">
                  <p className="text-sm font-medium text-gray-700 truncate">
                    {ENGINE_LABELS[engine] || engine}
                  </p>
                  <p className="text-xs text-gray-400">
                    {engineStats.current?.result_count ?? 0} scans
                  </p>
                </div>
                <div className="flex-1">
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className={`h-2 rounded-full transition-all ${
                        pct === null ? "bg-gray-200" : pct >= 70 ? "bg-green-400" : pct >= 40 ? "bg-yellow-400" : "bg-red-400"
                      }`}
                      style={{ width: pct !== null ? `${pct}%` : "0%" }}
                    />
                  </div>
                  {delta !== null && delta !== undefined && (
                    <p className={`text-xs mt-0.5 ${delta > 0.01 ? "text-green-500" : delta < -0.01 ? "text-red-400" : "text-gray-400"}`}>
                      {delta > 0 ? "+" : ""}{Math.round(delta * 100)}pp vs prior 7d
                    </p>
                  )}
                </div>
                <div className={`text-sm font-bold w-12 text-right shrink-0 ${scoreColor(score)}`}>
                  {fmtScore(score)}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </SectionCard>
  );
}

// ─── Prompt tracking card ─────────────────────────────────────────────────────

function PromptTrackingCard({ stats }) {
  const byPrompt = stats?.by_prompt ?? [];

  return (
    <SectionCard title="Prompt Tracking">
      {byPrompt.length === 0 ? (
        <p className="text-sm text-gray-400">No prompt data yet. Run some scans to see per-prompt visibility.</p>
      ) : (
        <div className="space-y-3">
          {byPrompt.slice(0, 8).map((p) => {
            const score = p.current?.score ?? null;
            const pct = score !== null ? Math.round(score * 100) : 0;
            const delta = p.trend_delta;

            return (
              <div key={p.prompt_text} className="flex items-start gap-4">
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-700 truncate" title={p.prompt_text}>
                    {p.prompt_text}
                  </p>
                  <div className="flex items-center gap-3 mt-1">
                    <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-1.5 rounded-full ${pct >= 70 ? "bg-green-400" : pct >= 40 ? "bg-yellow-400" : "bg-red-300"}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    {delta !== null && delta !== undefined && Math.abs(delta) >= 0.01 && (
                      <span className={`text-xs shrink-0 ${delta > 0 ? "text-green-500" : "text-red-400"}`}>
                        {delta > 0 ? "↑" : "↓"}{Math.abs(Math.round(delta * 100))}pp
                      </span>
                    )}
                  </div>
                </div>
                <div className={`text-sm font-bold shrink-0 ${scoreColor(score)}`}>
                  {fmtScore(score)}
                </div>
              </div>
            );
          })}
          {byPrompt.length > 8 && (
            <p className="text-xs text-gray-400 pt-1">+{byPrompt.length - 8} more prompts tracked</p>
          )}
        </div>
      )}
    </SectionCard>
  );
}

// ─── Competitor gap card ──────────────────────────────────────────────────────

function CompetitorGapCard({ stats }) {
  const gaps = stats?.competitor_gap ?? [];
  const maxCitations = gaps.length > 0 ? Math.max(...gaps.map((g) => g.citation_count), 1) : 1;

  return (
    <SectionCard title="Competitor Gap Analysis">
      {gaps.length === 0 ? (
        <p className="text-sm text-gray-400">
          Add competitors to see how often they appear in AI citations.
        </p>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-gray-400">
            Citation count in AI responses across all scans.
          </p>
          {gaps.map((gap) => {
            const barPct = Math.round((gap.citation_count / maxCitations) * 100);
            return (
              <div key={gap.website_url} className="flex items-center gap-4">
                <div className="w-32 shrink-0">
                  <p className="text-sm font-medium text-gray-700 truncate">{gap.name}</p>
                  <a
                    href={gap.website_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-gray-400 hover:text-brand-500 truncate block"
                  >
                    {gap.website_url.replace(/^https?:\/\/(www\.)?/, "")}
                  </a>
                </div>
                <div className="flex-1">
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-2 bg-orange-300 rounded-full transition-all"
                      style={{ width: `${barPct}%` }}
                    />
                  </div>
                </div>
                <div className="text-sm font-semibold text-gray-700 w-12 text-right shrink-0">
                  {gap.citation_count}
                  <span className="text-xs font-normal text-gray-400 ml-0.5">cit.</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </SectionCard>
  );
}

// ─── Citation tracking card ───────────────────────────────────────────────────

function CitationTrackingCard({ stats }) {
  const citations = stats?.citations ?? [];

  return (
    <SectionCard title="Citation Tracking">
      {citations.length === 0 ? (
        <p className="text-sm text-gray-400">
          No brand citations yet. Run scans to see where AI engines cite your brand.
        </p>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-gray-400">
            URLs where your brand was cited in AI responses (most recent first).
          </p>
          {citations.map((c, i) => (
            <div key={i} className="flex items-start gap-3 py-2.5 border-b border-gray-50 last:border-0">
              <div className="flex-1 min-w-0">
                <a
                  href={c.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-medium text-brand-600 hover:underline truncate block"
                  title={c.url}
                >
                  {c.title || c.domain || c.url}
                </a>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-xs text-gray-400 truncate" title={c.prompt_text}>
                    "{c.prompt_text.length > 60 ? c.prompt_text.slice(0, 60) + "…" : c.prompt_text}"
                  </span>
                </div>
              </div>
              <div className="shrink-0 flex flex-col items-end gap-1">
                <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
                  {ENGINE_LABELS[c.engine] || c.engine}
                </span>
                <span className="text-xs text-gray-400">{fmtRelTime(c.cited_at)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </SectionCard>
  );
}

// ─── GEO scan + results card ──────────────────────────────────────────────────

const ENGINE_OPTIONS = Object.entries(ENGINE_LABELS);

function GEOResultsCard({ projectId, onScanComplete }) {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [scanForm, setScanForm] = useState({ prompt_text: "", engine: "chatgpt" });
  const [scanError, setScanError] = useState("");
  const [scanQueued, setScanQueued] = useState(false);
  const lastFetchRef = useRef(null);

  const fetchResults = useCallback(async () => {
    try {
      const { data } = await api.get(`/api/projects/${projectId}/prompt-results/`);
      setResults(data);
      lastFetchRef.current = new Date().toISOString();
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { fetchResults(); }, [fetchResults]);

  // Auto-refresh every 30s
  useEffect(() => {
    const id = setInterval(fetchResults, 30000);
    return () => clearInterval(id);
  }, [fetchResults]);

  async function handleScan(e) {
    e.preventDefault();
    if (!scanForm.prompt_text.trim()) return;
    setScanning(true);
    setScanError("");
    setScanQueued(false);
    try {
      await api.post(`/api/projects/${projectId}/prompt-results/run`, scanForm);
      setScanQueued(true);
      setScanForm((f) => ({ ...f, prompt_text: "" }));
      if (onScanComplete) onScanComplete();
    } catch (err) {
      setScanError(err.response?.data?.detail || "Failed to enqueue scan");
    } finally {
      setScanning(false);
    }
  }

  return (
    <SectionCard
      title="GEO Scans"
      lastUpdated={lastFetchRef.current}
      loading={loading}
      action={
        <button
          onClick={fetchResults}
          disabled={loading}
          className="text-xs text-gray-400 hover:text-brand-500 transition disabled:opacity-40"
          title="Refresh"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      }
    >
      <form onSubmit={handleScan} className="flex gap-2 mb-5">
        <input
          type="text"
          value={scanForm.prompt_text}
          onChange={(e) => setScanForm((f) => ({ ...f, prompt_text: e.target.value }))}
          placeholder="Enter a prompt to scan (e.g. best CRM tools for startups)"
          className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
        <select
          value={scanForm.engine}
          onChange={(e) => setScanForm((f) => ({ ...f, engine: e.target.value }))}
          className="border border-gray-200 rounded-lg px-2 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
        >
          {ENGINE_OPTIONS.map(([val, label]) => (
            <option key={val} value={val}>{label}</option>
          ))}
        </select>
        <button
          type="submit"
          disabled={scanning || !scanForm.prompt_text.trim()}
          className="bg-brand-500 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-brand-600 disabled:opacity-50 transition whitespace-nowrap"
        >
          {scanning ? "Queuing…" : "Run scan"}
        </button>
      </form>
      {scanError && <ErrorMsg msg={scanError} />}
      {scanQueued && (
        <p className="text-xs text-green-600 mb-4">
          Scan queued — results will appear below once the worker finishes. Page auto-refreshes every 30s.
        </p>
      )}

      {loading && results.length === 0 ? (
        <p className="text-sm text-gray-400">Loading results…</p>
      ) : results.length === 0 ? (
        <p className="text-sm text-gray-400">No scans yet. Run your first scan above.</p>
      ) : (
        <div className="space-y-3">
          {results.map((r) => (
            <div
              key={r.id}
              className="border border-gray-100 rounded-xl p-4 hover:border-gray-200 transition"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800 truncate">{r.prompt_text}</p>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
                      {ENGINE_LABELS[r.engine] || r.engine}
                    </span>
                    <span className="text-xs text-gray-400">
                      {new Date(r.queried_at).toLocaleString()}
                    </span>
                  </div>
                </div>
                <div className={`text-right shrink-0 px-3 py-2 rounded-xl ${scoreBg(r.visibility_score)}`}>
                  <p className={`text-lg font-bold ${scoreColor(r.visibility_score)}`}>
                    {fmtScore(r.visibility_score)}
                  </p>
                  <p className="text-xs text-gray-400">visibility</p>
                </div>
              </div>

              <div className="flex items-center gap-4 mt-3">
                <span
                  className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                    r.brand_mentioned
                      ? "bg-green-50 text-green-700"
                      : "bg-gray-100 text-gray-500"
                  }`}
                >
                  {r.brand_mentioned ? "Brand mentioned" : "Not mentioned"}
                </span>
                {r.citations.length > 0 && (
                  <span className="text-xs text-gray-400">
                    {r.citations.length} citation{r.citations.length !== 1 ? "s" : ""}
                    {r.citations.some((c) => c.is_brand_domain) && (
                      <span className="ml-1 text-green-600 font-medium">· brand cited</span>
                    )}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </SectionCard>
  );
}

// ─── Data freshness banner ────────────────────────────────────────────────────

function DataFreshnessBanner({ status, onRefresh, refreshing }) {
  if (!status) return null;
  const { is_running, is_stale, last_run_at } = status;

  if (is_running) {
    return (
      <div className="flex items-center gap-2 bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 mb-6 text-sm text-blue-700">
        <span className="w-3 h-3 rounded-full border-2 border-blue-400 border-t-transparent animate-spin inline-block shrink-0" />
        <span>AI scans are running — data will update shortly.</span>
      </div>
    );
  }

  if (is_stale) {
    return (
      <div className="flex items-center justify-between bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 mb-6">
        <div className="flex items-center gap-2 text-sm text-amber-800">
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
          </svg>
          <span>
            Data is stale
            {last_run_at ? ` — last run ${fmtRelTime(last_run_at)}` : " — no runs yet"}.
          </span>
        </div>
        <button
          onClick={onRefresh}
          disabled={refreshing}
          className="text-xs font-medium text-amber-700 hover:text-amber-900 bg-amber-100 hover:bg-amber-200 px-3 py-1.5 rounded-lg transition disabled:opacity-50"
        >
          {refreshing ? "Queuing…" : "Refresh now"}
        </button>
      </div>
    );
  }

  return null;
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────

export default function Dashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [project, setProject] = useState(null);
  const [brand, setBrand] = useState(null);
  const [step, setStep] = useState("loading");
  const [stats, setStats] = useState(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [dataStatus, setDataStatus] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState("");

  const fetchStats = useCallback(async (projectId) => {
    setStatsLoading(true);
    try {
      const { data } = await api.get(`/api/projects/${projectId}/dashboard`);
      setStats(data);
    } catch {
      // silently fail — stats are non-critical
    } finally {
      setStatsLoading(false);
    }
  }, []);

  const fetchStatus = useCallback(async (projectId) => {
    try {
      const { data } = await api.get(`/api/projects/${projectId}/dashboard/status`);
      setDataStatus(data);
    } catch {
      // silently fail
    }
  }, []);

  useEffect(() => {
    async function bootstrap() {
      try {
        const { data: projects } = await api.get("/api/projects/");
        if (projects.length === 0) {
          setStep("create_project");
          return;
        }
        const proj = projects[0];
        setProject(proj);
        try {
          const { data: b } = await api.get(`/api/projects/${proj.id}/brand/`);
          setBrand(b);
          setStep("ready");
          fetchStats(proj.id);
          fetchStatus(proj.id);
        } catch (err) {
          if (err.response?.status === 404) {
            setStep("setup_brand");
          } else {
            setStep("ready");
            fetchStats(proj.id);
            fetchStatus(proj.id);
          }
        }
      } catch {
        setStep("create_project");
      }
    }
    bootstrap();
  }, [fetchStats, fetchStatus]);

  // Poll status: every 10s while running, every 60s otherwise
  useEffect(() => {
    if (step !== "ready" || !project) return;
    const interval = dataStatus?.is_running ? 10000 : 60000;
    const id = setInterval(() => fetchStatus(project.id), interval);
    return () => clearInterval(id);
  }, [step, project, dataStatus?.is_running, fetchStatus]);

  // Re-fetch stats when running flips to false
  const prevRunning = useRef(null);
  useEffect(() => {
    if (prevRunning.current === true && dataStatus?.is_running === false && project) {
      fetchStats(project.id);
    }
    prevRunning.current = dataStatus?.is_running ?? null;
  }, [dataStatus?.is_running, project, fetchStats]);

  // Auto-refresh stats every 30s when on ready step
  useEffect(() => {
    if (step !== "ready" || !project) return;
    const id = setInterval(() => fetchStats(project.id), 30000);
    return () => clearInterval(id);
  }, [step, project, fetchStats]);

  async function handleManualRefresh() {
    if (!project) return;
    setRefreshing(true);
    setRefreshError("");
    try {
      await api.post(`/api/projects/${project.id}/dashboard/refresh`);
      await fetchStatus(project.id);
    } catch (err) {
      if (err.response?.status === 429) {
        setRefreshError("Refresh is throttled — once per hour. Try again later.");
      } else {
        setRefreshError("Failed to trigger refresh.");
      }
    } finally {
      setRefreshing(false);
    }
  }

  function handleLogout() {
    logout();
    navigate("/login");
  }

  function handleProjectCreated(proj) {
    setProject(proj);
    setStep("setup_brand");
  }

  function handleBrandSetup(b) {
    setBrand(b);
    setStep("ready");
    if (project) {
      fetchStats(project.id);
      fetchStatus(project.id);
    }
  }

  function handleScanComplete() {
    if (project) fetchStats(project.id);
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header user={user} onLogout={handleLogout} />

      <main className="max-w-5xl mx-auto px-6 py-10">
        {!user?.is_verified && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-xl px-5 py-4 mb-8 text-sm text-yellow-800">
            Please check your email and verify your account to get full access.
          </div>
        )}

        {step === "loading" && (
          <p className="text-sm text-gray-400 text-center mt-24">Loading…</p>
        )}

        {step === "create_project" && (
          <CreateProjectStep onCreated={handleProjectCreated} />
        )}

        {step === "setup_brand" && project && (
          <BrandSetupStep projectId={project.id} onComplete={handleBrandSetup} />
        )}

        {step === "ready" && project && (
          <>
            <div className="flex items-start justify-between mb-8">
              <div>
                <h2 className="text-2xl font-semibold text-gray-900">{project.name}</h2>
                <p className="text-sm text-gray-400 mt-0.5">GEO visibility dashboard</p>
              </div>
              <div className="flex flex-col items-end gap-1">
                <button
                  onClick={handleManualRefresh}
                  disabled={refreshing || dataStatus?.is_running}
                  className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-brand-500 bg-white border border-gray-200 rounded-lg px-3 py-1.5 transition disabled:opacity-40"
                  title="Trigger a fresh AI scan run"
                >
                  <svg className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  {refreshing ? "Queuing…" : "Refresh data"}
                </button>
                {dataStatus?.last_run_at && (
                  <span className="text-xs text-gray-400">
                    Last run {fmtRelTime(dataStatus.last_run_at)}
                  </span>
                )}
                {refreshError && (
                  <span className="text-xs text-red-500">{refreshError}</span>
                )}
              </div>
            </div>

            <DataFreshnessBanner
              status={dataStatus}
              onRefresh={handleManualRefresh}
              refreshing={refreshing}
            />

            {/* Hero: visibility score */}
            <div className="mb-6">
              <VisibilityScoreCard
                stats={stats}
                loading={statsLoading || dataStatus?.is_running}
                onRefresh={() => fetchStats(project.id)}
              />
            </div>

            {/* Engine breakdown + competitor gap side-by-side */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
              <EngineBreakdownCard stats={stats} />
              <CompetitorGapCard stats={stats} />
            </div>

            {/* Prompt tracking */}
            <div className="mb-6">
              <PromptTrackingCard stats={stats} />
            </div>

            {/* Citation tracking */}
            <div className="mb-6">
              <CitationTrackingCard stats={stats} />
            </div>

            {/* Config cards */}
            <div className="space-y-6">
              {brand ? (
                <BrandCard brand={brand} projectId={project.id} onUpdated={setBrand} />
              ) : (
                <BrandSetupStep projectId={project.id} onComplete={handleBrandSetup} />
              )}
              <CompetitorsCard projectId={project.id} />
              <GEOResultsCard projectId={project.id} onScanComplete={handleScanComplete} />
            </div>
          </>
        )}
      </main>
    </div>
  );
}

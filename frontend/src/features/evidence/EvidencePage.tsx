import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { evidenceApi, type AnalysisRecord } from '@/api/v2'
import { AppShell } from '@/components/AppShell'
import { Reveal } from '@/components/motion/Reveal'
import { attributeLabel } from '@/data/attributes'
import {
  BarsWithCI,
  C,
  ForestChart,
  Legend,
  LineChart,
  NullHistogram,
  ReliabilityChart,
  SERIES_COLORS,
  SourceBadge,
  ci,
  fmt,
} from './charts'

/* eslint-disable @typescript-eslint/no-explicit-any -- payloads are the
   JSON written by cohab/analysis/reproduce.py; their shape is documented
   there and checked by its tests. */
type Any = any

function Section({
  title,
  record,
  lead,
  children,
}: {
  title: string
  record?: AnalysisRecord<Any>
  lead?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <Reveal className="min-w-0 bg-cohab-card border border-cohab-border rounded-2xl p-5 cohab-desktop:p-6">
      <div className="flex flex-wrap items-start justify-between gap-2 mb-1.5">
        <h2 className="text-[17px] font-semibold">{title}</h2>
        {record && <SourceBadge source={record.data_source} />}
      </div>
      {lead && <p className="text-[13px] leading-[1.55] text-cohab-muted mb-4 max-w-[760px]">{lead}</p>}
      {children}
    </Reveal>
  )
}

function Stat({ label, value, sub }: { label: string; value: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="bg-cohab-bg/40 border border-cohab-border-soft rounded-xl px-3.5 py-3">
      <div className="text-[22px] font-semibold tabular-nums leading-none">{value}</div>
      <div className="text-[11.5px] text-cohab-muted mt-1.5">{label}</div>
      {sub && <div className="text-[11px] text-cohab-subtle mt-0.5 tabular-nums">{sub}</div>}
    </div>
  )
}

function Empty({ what }: { what: string }) {
  return <p className="text-[13px] text-cohab-subtle">No {what} yet. Run <code>make reproduce</code> to generate it.</p>
}

export function EvidencePage() {
  const { data, isLoading, error } = useQuery({ queryKey: ['evidence', 'summary'], queryFn: evidenceApi.summary })
  const r = (k: string) => data?.[k] as AnalysisRecord<Any> | undefined

  const tier = r('tier')
  const lab = r('lab')
  const pairs = r('pairs')
  const power = r('power')
  const policy = r('policy_comparison')
  const misreport = r('misreporting')
  const stab = r('rank_stability')
  const fair = r('fairness_synthetic')
  const fairLive = r('fairness_live')
  const transfer = r('transfer')
  const anySynthetic = Object.values(data ?? {}).some((x) => x.data_source === 'dryrun')

  return (
    <AppShell>
      <div className="max-w-[1400px] mx-auto px-4 cohab-desktop:px-6 py-7 pb-14">
        <div className="flex flex-wrap items-end justify-between gap-3 mb-1">
          <h1 className="poster text-[64px]">Evidence</h1>
          <Link to="/evidence/playground" className="text-[13.5px] font-medium text-cohab-primary">
            Open the policy playground →
          </Link>
        </div>
        <p className="text-[13.5px] leading-[1.55] text-cohab-muted mb-5 max-w-[820px]">
          Every number below was produced by <code>make reproduce</code> from stored data with fixed seeds, and each
          panel says where its data came from. Simulation results follow from their stated assumptions. Nothing here
          claims that 90-day cohabitation improved: that outcome cannot be observed within the project.
        </p>
        {anySynthetic && (
          <div className="border border-cohab-accent bg-cohab-accent-tint rounded-2xl px-4 py-3 mb-5 text-[13px] text-cohab-warn max-w-[820px]">
            Study panels currently show a <strong>synthetic dry run</strong>: the pipeline run end to end on simulated
            raters with a planted answer. It shows the method works, not what people prefer.
          </div>
        )}

        {isLoading && <p className="text-cohab-muted">Loading…</p>}
        {error && <p className="text-cohab-accent">Couldn't load the evidence summary.</p>}

        {data && (
          <div className="grid gap-4 grid-cols-1 cohab-desktop:grid-cols-2 items-start">
            {/* 1. Sample and tier */}
            <Section title="Sample and tier" record={tier} lead="Gate 2 decides how much the study can claim. The tier rules were fixed before collection.">
              {tier ? (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                  <Stat label="Tier" value={tier.payload.tier} />
                  <Stat label="Raters kept" value={tier.payload.raters_kept} sub={`of ${tier.payload.raters_total}`} />
                  <Stat label="Complete pairs" value={tier.payload.complete_pairs} />
                  <Stat
                    label="Test–retest κ"
                    value={fmt(lab?.payload.reliability?.kappa, 2)}
                    sub={ci(lab?.payload.reliability?.kappa_ci, 2)}
                  />
                </div>
              ) : (
                <Empty what="study data" />
              )}
            </Section>

            {/* 2. Primary comparison */}
            <Section
              title="Primary comparison: learned vs expert"
              record={lab}
              lead="Pre-registered. Held-out raters only (grouped 5-fold CV), 95% intervals from resampling raters. A difference whose interval spans zero is reported as no reliable difference."
            >
              {lab?.payload.status === 'ok' ? (
                <>
                  <div className="grid grid-cols-2 gap-2.5 mb-4">
                    <Stat
                      label="Δ log loss (learned − expert, lower is better)"
                      value={fmt(lab.payload.cv.learned_minus_expert_log_loss.estimate, 4)}
                      sub={ci(lab.payload.cv.learned_minus_expert_log_loss.ci, 4)}
                    />
                    <Stat
                      label="Δ accuracy (learned − expert)"
                      value={fmt(lab.payload.cv.learned_minus_expert_accuracy.estimate, 3)}
                      sub={ci(lab.payload.cv.learned_minus_expert_accuracy.ci, 3)}
                    />
                  </div>
                  <BarsWithCI
                    min={0.4}
                    max={1}
                    highlight={['Expert', 'Learned']}
                    reference={
                      lab.payload.reliability?.noise_ceiling_accuracy
                        ? { value: lab.payload.reliability.noise_ceiling_accuracy, label: 'noise ceiling' }
                        : undefined
                    }
                    items={[
                      ['random', 'Random'],
                      ['single_attribute', 'Best single'],
                      ['uniform', 'Uniform'],
                      ['expert', 'Expert'],
                      ['learned', 'Learned'],
                    ].map(([k, label]) => ({
                      label,
                      value: lab.payload.cv.scorers[k].accuracy,
                      low: lab.payload.cv.scorers[k].accuracy_ci[0],
                      high: lab.payload.cv.scorers[k].accuracy_ci[1],
                    }))}
                  />
                  <p className="text-[12px] text-cohab-subtle mt-2">
                    Held-out pairwise accuracy. The noise ceiling is the best any model of stable preferences can reach,
                    estimated from repeated pairs.
                  </p>
                </>
              ) : (
                <Empty what="study comparison" />
              )}
            </Section>

            {/* 3. Weights */}
            <Section
              title="What people weigh"
              record={lab}
              lead="Learned weights (dot, 95% rater-bootstrap interval) against the expert prior (square). Fitted with shrinkage toward the expert values, so little data returns the expert weights."
            >
              {lab?.payload.status === 'ok' ? (
                <>
                  <ForestChart
                    labels={lab.payload.weights.attributes.map(attributeLabel)}
                    expert={lab.payload.weights.expert}
                    learned={lab.payload.weights.learned}
                    low={lab.payload.weights.ci_low}
                    high={lab.payload.weights.ci_high}
                  />
                  <div className="flex flex-wrap items-center justify-between gap-2 mt-2">
                    <Legend items={[{ label: 'Learned', color: C.primary }, { label: 'Expert v2', color: C.expert, shape: 'square' }]} />
                    <span className="text-[12px] text-cohab-muted">
                      "Top 3" boost: v1 uses 1.5×, estimated {fmt(lab.payload.weights.importance_multiplier, 2)}×{' '}
                      {ci(lab.payload.weights.importance_multiplier_ci, 2)}
                    </span>
                  </div>
                </>
              ) : (
                <Empty what="fitted weights" />
              )}
            </Section>

            {/* 4. Calibration */}
            <Section
              title="Calibration: what a score means"
              record={lab}
              lead="Out-of-fold probability that a rater would message a profile, from its directional score. Only this one-sided probability is supported by the data; mutual interest and 90-day outcomes are not shown."
            >
              {lab?.payload.status === 'ok' ? (
                <div className="grid sm:grid-cols-[minmax(0,320px)_1fr] gap-4 items-center">
                  <ReliabilityChart
                    series={[
                      { label: 'Raw score', color: C.expert, bins: lab.payload.calibration.raw_score_as_probability.bins },
                      { label: 'Isotonic', color: C.primary, bins: lab.payload.calibration.calibrated.bins },
                    ]}
                  />
                  <div className="flex flex-col gap-2.5">
                    <Stat label="ECE, calibrated (target < 0.05)" value={fmt(lab.payload.calibration.calibrated.ece)} />
                    <Stat label="ECE, raw score as probability" value={fmt(lab.payload.calibration.raw_score_as_probability.ece)} />
                    <Stat label="Brier, calibrated" value={fmt(lab.payload.calibration.calibrated.brier)} />
                    <Legend items={[{ label: 'Raw score', color: C.expert }, { label: 'Isotonic', color: C.primary }]} />
                  </div>
                </div>
              ) : (
                <Empty what="calibration" />
              )}
            </Section>

            {/* 5. Roommate pairs */}
            <Section
              title="Real roommates: does the score track how it went?"
              record={pairs}
              lead="Each person answered alone. Real pairs are compared with the same people randomly re-paired; satisfied pairs with dissatisfied ones."
            >
              {pairs?.payload.expert?.status === 'ok' ? (
                <PairsBody p={pairs.payload.expert} />
              ) : (
                <p className="text-[13px] text-cohab-subtle">
                  Not enough complete pairs yet ({pairs?.payload.expert?.n_pairs ?? 0}). Reported once at least 4 exist.
                </p>
              )}
            </Section>

            {/* 6. Power */}
            <Section
              title="Power: how many raters the study needs"
              record={power}
              lead="Simulated raters on the real design, through the full pipeline. Each line is a way real people might differ from the model."
            >
              {power ? (
                <>
                  <LineChart
                    xLabel="Raters"
                    yLabel="P(learned reliably beats expert)"
                    reference={0.8}
                    series={power.payload.scenarios.map((s: Any, i: number) => ({
                      label: s.label,
                      color: SERIES_COLORS[i % SERIES_COLORS.length],
                      points: s.rows.map((r: Any) => [r.n_raters, r.p_learned_reliably_better]),
                    }))}
                  />
                  <Legend
                    items={power.payload.scenarios.map((s: Any, i: number) => ({
                      label: `${s.label}${power.payload.minimum_raters_80pct?.[s.key] ? ` (80% at ${power.payload.minimum_raters_80pct[s.key]})` : ''}`,
                      color: SERIES_COLORS[i % SERIES_COLORS.length],
                    }))}
                  />
                </>
              ) : (
                <Empty what="power study" />
              )}
            </Section>

            {/* 7. Policy comparison */}
            <Section
              title="Policy comparison"
              record={policy}
              lead={policy ? `${policy.payload.runs} seeded worlds of ${policy.payload.config.n_agents} agents, mean with 95% CI. Hidden true compatibility differs from every policy's model.` : undefined}
            >
              {policy ? <PolicyTable p={policy.payload} /> : <Empty what="simulation" />}
              {misreport && (
                <div className="mt-4">
                  <p className="text-[12.5px] font-medium text-cohab-muted mb-1.5">If people flatter themselves on gameable answers</p>
                  <div className="overflow-x-auto"><table className="w-full text-[12.5px] tabular-nums min-w-[300px]">
                    <thead className="text-cohab-subtle text-left">
                      <tr>
                        <th className="font-normal py-1">Share misreporting</th>
                        <th className="font-normal">Expert welfare</th>
                        <th className="font-normal">Overlap with oracle</th>
                      </tr>
                    </thead>
                    <tbody>
                      {misreport.payload.rows.map((row: Any) => (
                        <tr key={row.misreport_share} className="border-t border-cohab-border-soft">
                          <td className="py-1">{Math.round(row.misreport_share * 100)}%</td>
                          <td>{fmt(row.expert_welfare.mean)}</td>
                          <td>{fmt(row.expert_overlap_with_oracle.mean)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table></div>
                </div>
              )}
            </Section>

            {/* 8. Rank stability */}
            <Section
              title="Rank stability"
              record={stab}
              lead="How much each person's top 5 moves when the weights are perturbed. Higher concentration means more confidence in the expert values. This is what drives the 'effectively tied' hint on the match screen."
            >
              {stab ? (
                <div className="overflow-x-auto"><table className="w-full text-[12.5px] tabular-nums min-w-[300px]">
                  <thead className="text-cohab-subtle text-left">
                    <tr>
                      <th className="font-normal py-1">Weight uncertainty</th>
                      <th className="font-normal">Top-5 Jaccard</th>
                      <th className="font-normal">P(#1 changes)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(stab.payload.expert_prior).map(([conc, s]: [string, Any]) => (
                      <tr key={conc} className="border-t border-cohab-border-soft">
                        <td className="py-1">Dirichlet prior, concentration {conc}</td>
                        <td>{fmt(s.topk_jaccard_mean)}</td>
                        <td>{fmt(s.p_first_changes_mean)}</td>
                      </tr>
                    ))}
                    {stab.payload.learned_bootstrap && (
                      <tr className="border-t border-cohab-border-soft font-medium">
                        <td className="py-1">Learned weights, rater bootstrap</td>
                        <td>{fmt(stab.payload.learned_bootstrap.topk_jaccard_mean)}</td>
                        <td>{fmt(stab.payload.learned_bootstrap.p_first_changes_mean)}</td>
                      </tr>
                    )}
                  </tbody>
                </table></div>
              ) : (
                <Empty what="stability analysis" />
              )}
            </Section>

            {/* 9. Fairness */}
            <Section
              title="Fairness audit"
              record={fair}
              lead="Group ratios to the overall mean. Outside 0.8–1.25 is flagged for a person to look at, never asserted as discrimination: gaps can come from what people ask for as much as from the system."
            >
              {fair ? <FairnessBody f={fair.payload} /> : <Empty what="fairness audit" />}
              {fairLive && <p className="text-[12px] text-cohab-subtle mt-2">A live-pool audit (aggregate only) is also stored.</p>}
            </Section>

            {/* 10. Transfer */}
            <Section
              title="Transfer test on public data"
              record={transfer}
              lead="Columbia speed-dating experiment: real two-sided choices with stated attribute importance. Tests the reciprocal-scoring machinery, not Cohab's roommate weights."
            >
              {transfer?.payload.status === 'ok' ? (
                <TransferBody t={transfer.payload} />
              ) : (
                <p className="text-[13px] text-cohab-subtle">
                  Dataset not present. {transfer?.payload.how_to_get} Expected at <code>{transfer?.payload.expected_path}</code>.
                </p>
              )}
            </Section>
          </div>
        )}
      </div>
    </AppShell>
  )
}

function PairsBody({ p }: { p: Any }) {
  const kg = p.known_groups
  return (
    <>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mb-4">
        <Stat label="Pairs" value={p.n_pairs} />
        <Stat label="Score gap, satisfied − not" value={fmt(kg.difference)} sub={ci(kg.difference_ci)} />
        <Stat label="Spearman ρ, score vs satisfaction" value={fmt(kg.spearman_rho, 2)} sub={ci(kg.spearman_ci, 2)} />
        <Stat label="Permutation p (one-sided)" value={fmt(p.permutation.p_value_one_sided, 3)} />
      </div>
      <NullHistogram counts={p.permutation.histogram} edges={p.permutation.histogram_edges} observed={p.permutation.real_mean} />
      <p className="text-[12px] text-cohab-subtle mt-1 mb-4">Mean score of real pairs against 5,000 random re-pairings of the same people.</p>
      <p className="text-[12.5px] font-medium text-cohab-muted mb-1.5">Self-report inflation (how people describe themselves vs how their roommate describes them)</p>
      <div className="overflow-x-auto"><table className="w-full text-[12.5px] tabular-nums min-w-[300px]">
        <thead className="text-cohab-subtle text-left">
          <tr>
            <th className="font-normal py-1">Item</th>
            <th className="font-normal">Agreement</th>
            <th className="font-normal">Steps more flattering</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(p.self_report_inflation).map(([f, v]: [string, Any]) => (
            <tr key={f} className="border-t border-cohab-border-soft">
              <td className="py-1">{f.replace(/_/g, ' ')}</td>
              <td>{Math.round(v.agreement * 100)}%</td>
              <td>
                {v.mean_inflation_steps != null ? `${fmt(v.mean_inflation_steps, 2)} ${ci(v.inflation_ci, 2)}` : 'not ordinal'}
              </td>
            </tr>
          ))}
        </tbody>
      </table></div>
      <ul className="text-[11.5px] text-cohab-subtle mt-3 list-disc pl-4">
        {p.limitations.map((l: string) => (
          <li key={l}>{l}</li>
        ))}
      </ul>
    </>
  )
}

const POLICY_LABEL: Record<string, string> = { random: 'Random eligible', expert: 'Expert weights', learned: 'Learned weights', oracle: 'Oracle (true)' }

function PolicyTable({ p }: { p: Any }) {
  const metrics: [string, string][] = [
    ['welfare_per_agent', 'Welfare'],
    ['match_rate', 'Match rate'],
    ['top10_overlap_with_oracle', 'Overlap w/ oracle'],
    ['exposure_gini', 'Exposure Gini'],
  ]
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[12.5px] tabular-nums min-w-[480px]">
        <thead className="text-cohab-subtle text-left">
          <tr>
            <th className="font-normal py-1">Policy</th>
            {metrics.map(([, l]) => (
              <th key={l} className="font-normal">
                {l}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Object.entries(p.table).map(([pol, row]: [string, Any]) => (
            <tr key={pol} className="border-t border-cohab-border-soft">
              <td className="py-1.5 font-medium">{POLICY_LABEL[pol] ?? pol}</td>
              {metrics.map(([m]) => (
                <td key={m}>
                  {fmt(row[m].mean)}
                  <span className="text-cohab-subtle text-[11px]"> ±{fmt((row[m].ci95[1] - row[m].ci95[0]) / 2, 3)}</span>
                </td>
              ))}
            </tr>
          ))}
          {p.irving_expert?.match_rate?.mean != null && (
            <tr className="border-t border-cohab-border-soft text-cohab-muted">
              <td className="py-1.5">Irving assignment*</td>
              <td>{fmt(p.irving_expert.welfare_per_agent.mean)}</td>
              <td>{fmt(p.irving_expert.match_rate.mean)}</td>
              <td colSpan={2}>stable matching in {Math.round(p.irving_expert.share_runs_with_stable_matching * 100)}% of worlds</td>
            </tr>
          )}
        </tbody>
      </table>
      <p className="text-[11.5px] text-cohab-subtle mt-2">
        *Irving's stable roommates assigns everyone and assumes they all accept. Shown as a reference point only: Cohab
        ranks and explains, it never assigns.
      </p>
    </div>
  )
}

function FairnessBody({ f }: { f: Any }) {
  return (
    <div className="flex flex-col gap-3">
      {Object.entries(f.groupings).map(([name, g]: [string, Any]) => (
        <div key={name}>
          <p className="text-[12.5px] font-medium text-cohab-muted mb-1">{name.replace(/_/g, ' ')}</p>
          <div className="overflow-x-auto"><table className="w-full text-[12.5px] tabular-nums min-w-[300px]">
            <tbody>
              {g.table.map((row: Any) => (
                <tr key={row.group} className="border-t border-cohab-border-soft">
                  <td className="py-1 w-[34%]">{row.group}</td>
                  <td className="text-cohab-subtle">n {row.n}</td>
                  <td>pass {fmt(row.pass_rate_ratio, 2)}</td>
                  <td>exposure {fmt(row.exposure_ratio, 2)}</td>
                  <td className="text-right">{row.flag ? <span className="text-cohab-accent font-medium">flag</span> : <span className="text-cohab-subtle">ok</span>}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        </div>
      ))}
      <div>
        <p className="text-[12.5px] font-medium text-cohab-muted mb-1">Counterfactual: no gender-preference constraint</p>
        <div className="overflow-x-auto"><table className="w-full text-[12.5px] tabular-nums min-w-[300px]">
          <tbody>
            {f.counterfactual_no_gender_preference.map((row: Any) => (
              <tr key={row.gender} className="border-t border-cohab-border-soft">
                <td className="py-1 w-[34%]">{row.gender}</td>
                <td>
                  median pool {row.median_pool_before} → {row.median_pool_after}
                </td>
                <td>
                  exposure {fmt(row.mean_exposure_before, 1)} → {fmt(row.mean_exposure_after, 1)}
                </td>
              </tr>
            ))}
          </tbody>
        </table></div>
      </div>
    </div>
  )
}

function TransferBody({ t }: { t: Any }) {
  const a = t.reciprocal.auc
  const svr = t.stated_vs_revealed
  return (
    <>
      <p className="text-[12.5px] font-medium text-cohab-muted mb-1.5">Predicting a mutual yes from two directional scores (AUC)</p>
      <BarsWithCI
        min={0.5}
        max={Math.min(1, Math.max(...Object.values(a).map((v: Any) => v.ci[1])) + 0.05)}
        highlight={['harmonic']}
        items={Object.entries(a).map(([k, v]: [string, Any]) => ({ label: k, value: v.auc, low: v.ci[0], high: v.ci[1] }))}
      />
      <div className="grid grid-cols-2 gap-2.5 mt-3">
        <Stat label="Harmonic − arithmetic AUC" value={fmt(t.reciprocal.harmonic_minus_arithmetic.estimate)} sub={ci(t.reciprocal.harmonic_minus_arithmetic.ci)} />
        <Stat label="Revealed − stated weights AUC" value={fmt(svr.revealed_minus_stated_auc.estimate)} sub={ci(svr.revealed_minus_stated_auc.ci)} />
      </div>
      <p className="text-[11.5px] text-cohab-subtle mt-2">{t.caveat}</p>
    </>
  )
}

# Bundle: systems

Load when the target is an architecture, design, or infrastructure document. The finance section is self-contained and loads alone when the money, estimates, or SLA signature fires.

## failure-modes
- Single points of failure: any component whose loss stops the system, with no stated degraded mode.
- Failure handling described for components but not for the links between them: partitions, timeouts, retries.
- Recovery steps that assume the failed component is still reachable.
- Availability claims with no stated error budget.
Anchor: the component or link, named, plus the missing handling.
False positive to avoid: flagging a stated and accepted risk as an omission.

## scalability
- Load figures asserted with no source, unit, or time window.
- A bottleneck sized for current load in a document that projects growth elsewhere.
- Horizontal scaling claimed for a component holding unshared state.
- Capacity and sizing maths that does not reproduce from the stated inputs. Scope: this lens owns capacity maths; analytics and metric numbers belong to ml.md metric-provenance.
Anchor: the figure or claim, quoted, plus the input that fails to support it.

## sys-integration
- Two components whose interface is described differently on each side. Code-level signature drift belongs to code.md integration; this lens owns component contracts, protocols, and data ownership.
- Data owned by no component, or by two.
- Synchronous calls across a boundary the document elsewhere calls unreliable.
- Versioning or migration path absent for an interface expected to change.
Anchor: both descriptions of the interface, cited.

## operability
- A failure mode flagged above with no signal that would reveal it in production.
- Rollback undefined for any change path the document introduces.
- Manual steps inside a procedure the document calls automated.
- Runbook actions requiring access the on-call role is not stated to have.
Anchor: the procedure or gap, named; absence findings follow the protocol's anchor rule.

## finance
Self-contained: apply without the lenses above when loaded alone. Invariant: this section must not reference any other lens, bundle, or protocol phase; a cross-reference here is a defect. When the money signature fired, this section is exempt from the lens-cap drop order.
- Costs or estimates with no derivation, unit, or date. A number without unit economics is a claim, not an estimate.
- SLA or SLO targets with no measurement method, error budget, or stated consequence for a miss.
- Totals that do not reproduce from their stated components.
- Growth assumptions applied to revenue but not to the costs that scale with it.
Anchor: the number, quoted, plus the derivation that is absent or fails.
False positive to avoid: demanding derivation for a figure the document marks as a placeholder.

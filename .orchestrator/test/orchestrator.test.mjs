import test from 'node:test';
import assert from 'node:assert/strict';
import { computeParallelBatches, qualityGateBlockers, statusReport, validateResult, validateRun } from '../src/core.mjs';
import config from '../config.json' with { type: 'json' };

function item(id, overrides = {}) {
  return {
    id,
    title: id,
    kind: 'specification',
    domains: ['platform'],
    objective: 'Doğrulanabilir çıktı üret.',
    responsibility: 'Yalnız atanmış kapsam.',
    inputs: [],
    outputs: ['artifact'],
    acceptanceCriteria: ['çıktı doğrulandı'],
    capabilities: [],
    relations: { dependsOn: [], reviews: [], verifies: [], revises: [], integrates: [] },
    risk: { level: 'low', reasons: [], approvalBoundaries: [] },
    execution: { mode: 'delegate', isolation: 'platform-default', readOnly: true, independent: false, writeScopes: [], preferredPlatforms: ['codex'], owner: null },
    status: 'ready', attempt: 0, resultRef: null,
    ...overrides
  };
}

function run(items) {
  return {
    schemaVersion: '1.0.0', runId: 'test-run', title: 'Test', goal: 'Test graph',
    createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(), revision: 0,
    context: { requiredPaths: [], optionalPaths: [], catalogSnapshot: null, assumptions: [] },
    constraints: [], policy: { requiresIntegration: false }, decisions: [], items
  };
}

test('valid read-only graph passes', () => {
  const result = validateRun(run([item('scope-item')]), config);
  assert.equal(result.valid, true);
});

test('dependency cycle fails', () => {
  const a = item('item-a'); const b = item('item-b');
  a.relations.dependsOn = ['item-b']; b.relations.dependsOn = ['item-a'];
  assert.equal(validateRun(run([a, b]), config).valid, false);
});

test('disjoint writers share a batch and overlapping writers serialize', () => {
  const writer = (id, scope) => item(id, { kind: 'implement', execution: { mode: 'delegate', isolation: 'worktree', readOnly: false, independent: false, writeScopes: [scope], preferredPlatforms: ['codex'], owner: null } });
  const batches = computeParallelBatches(run([writer('writer-a', 'packages/phase-1'), writer('writer-b', 'packages/phase-2'), writer('writer-c', 'packages/phase-1/src')]), config);
  assert.deepEqual(batches[0], ['writer-a', 'writer-b']);
  assert.deepEqual(batches[1], ['writer-c']);
});

test('pass result requires all acceptance evidence', () => {
  const work = item('verify-me'); const graph = run([work]);
  const result = { schemaVersion: '1.0.0', runId: graph.runId, itemId: work.id, agent: { platform: 'manual', identity: 'tester', sessionRef: null }, outcome: 'pass', summary: 'ok', artifacts: [], acceptance: [{ criterion: 'çıktı doğrulandı', status: 'not_verified', evidence: 'çalıştırılmadı' }], checks: [], risks: [], followUps: [], completedAt: new Date().toISOString() };
  assert.equal(validateResult(result, graph, work).valid, false);
});

test('status exposes safe batches', () => {
  const report = statusReport(run([item('ready-item')]), config);
  assert.deepEqual(report.batches, [['ready-item']]);
});

function delivery(id, revises = []) {
  const work = item(id, { kind: 'implement', status: 'done', resultRef: `results/${id}.json` });
  work.relations.revises = revises;
  const gate = (name, kind, relationName) => {
    const node = item(`${id}-${name}`, { kind, status: 'done', resultRef: `results/${id}-${name}.json` });
    node.execution.independent = true;
    node.relations.dependsOn = [id]; node.relations[relationName] = [id];
    return node;
  };
  const review = gate('review', 'review', 'reviews');
  const verify = gate('verify', 'verify', 'verifies');
  const integration = item(`${id}-integration`, { kind: 'integration', status: 'done', resultRef: `results/${id}-integration.json` });
  integration.relations.dependsOn = [review.id, verify.id];
  integration.relations.integrates = [id];
  return [work, review, verify, integration];
}

test('every gate blocks, including a failed security review after a passed review', () => {
  const items = delivery('original-item');
  const security = item('security-review', { kind: 'security-review', status: 'failed' });
  security.relations.reviews = ['original-item']; items.push(security);
  assert.deepEqual(qualityGateBlockers(run(items), config), [{ itemId: 'original-item', gate: 'review', gateItemId: 'security-review' }]);
});

test('a revision requires independent gates and integration before resolving failure', () => {
  for (const stage of ['implementation', 'review', 'verification', 'independence', 'integration', 'integration-links']) {
    const original = delivery('original-item'); original[0].status = 'failed'; original[1].status = 'failed';
    const revision = delivery('revision-item', ['original-item']);
    if (stage === 'implementation') revision[0].status = 'active';
    if (stage === 'review') revision[1].status = 'failed';
    if (stage === 'verification') revision[2].status = 'ready';
    if (stage === 'independence') revision[1].execution.independent = false;
    if (stage === 'integration') revision[3].status = 'ready';
    if (stage === 'integration-links') { revision[3].relations.dependsOn = []; revision[3].relations.integrates = ['revision-item']; }
    assert.ok(qualityGateBlockers(run([...original, ...revision]), config).some((blocker) => blocker.itemId === 'original-item'), stage);
  }
});

test('accepted revision chain resolves old failures and unrun old gates without rewriting history', () => {
  const original = delivery('original-item'); original[0].status = 'failed'; original[1].status = 'failed'; original[2].status = 'draft'; original[3].status = 'draft';
  const first = delivery('first-revision', ['original-item']); first[1].status = 'failed'; first[3].status = 'draft';
  const second = delivery('second-revision', ['first-revision']);
  const graph = run([...original, ...first, ...second]); const before = JSON.stringify(graph);
  assert.deepEqual(qualityGateBlockers(graph, config), []);
  assert.equal(JSON.stringify(graph), before);
  assert.equal(original[1].status, 'failed'); assert.equal(original[2].status, 'draft');
});

test('revision of one failed gate does not hide another failed gate', () => {
  const original = delivery('original-item'); original[1].status = 'failed'; original[2].status = 'failed';
  const reviewFix = delivery('review-fix', ['original-item-review']);
  assert.deepEqual(qualityGateBlockers(run([...original, ...reviewFix]), config), [{ itemId: 'original-item', gate: 'verify', gateItemId: 'original-item-verify' }]);
  const verifyFix = delivery('verify-fix', ['original-item-verify']);
  assert.deepEqual(qualityGateBlockers(run([...original, ...reviewFix, ...verifyFix]), config), []);
});

test('cyclic unfinished revisions cannot resolve failure or recurse indefinitely', () => {
  const original = delivery('original-item', ['revision-item']); original[1].status = 'failed';
  const revision = delivery('revision-item', ['original-item']); revision[1].status = 'failed';
  assert.equal(qualityGateBlockers(run([...original, ...revision]), config).length, 2);
});

test('a not_run check prevents a pass result', () => {
  const work = item('verify-me'); const graph = run([work]);
  const result = { schemaVersion: '1.0.0', runId: graph.runId, itemId: work.id, outcome: 'pass', acceptance: [{ criterion: 'çıktı doğrulandı', status: 'passed', evidence: 'artifact' }], checks: [{ name: 'mandatory browser', status: 'not_run', evidence: 'not executed' }] };
  assert.equal(validateResult(result, graph, work).valid, false);
});

function specialistGate(targetId, kind, status = 'done') {
  const node = item(`${targetId}-${kind}`, { kind, status, resultRef: `results/${targetId}-${kind}.json` });
  node.execution.independent = true;
  node.relations[kind.includes('review') ? 'reviews' : 'verifies'] = [targetId];
  node.relations.dependsOn = [targetId];
  return node;
}

test('generic revisions cannot bypass specialist gates directly or through a chain', () => {
  for (const kind of ['security-review', 'architecture-review', 'security-verify', 'test']) {
    for (const mode of ['whole-target', 'failed-gate', 'transitive']) {
      const original = delivery('original-item'); const specialist = specialistGate('original-item', kind, 'failed');
      const first = delivery('first-revision', [mode === 'failed-gate' ? specialist.id : 'original-item']);
      const graph = run([...original, specialist, ...first]);
      if (mode === 'transitive') {
        first[1].status = 'failed'; first[3].status = 'draft';
        graph.items.push(...delivery('second-revision', ['first-revision']));
      }
      assert.ok(qualityGateBlockers(graph, config).some((blocker) => blocker.gateItemId === specialist.id), `${kind}/${mode}`);
    }
  }
});

test('specialist revision requires the same kind, independent scope and integration link', () => {
  for (const kind of ['security-review', 'architecture-review', 'security-verify', 'test']) {
    const original = delivery('original-item'); const oldGate = specialistGate('original-item', kind, 'failed');
    const revision = delivery('revision-item', [oldGate.id]); const newGate = specialistGate('revision-item', kind);
    const graph = run([...original, oldGate, ...revision, newGate]);
    assert.ok(qualityGateBlockers(graph, config).some((blocker) => blocker.gateItemId === oldGate.id), 'unintegrated specialist cannot resolve history');
    revision[3].relations.dependsOn.push(newGate.id);
    assert.deepEqual(qualityGateBlockers(graph, config), []);
    newGate.execution.independent = false;
    assert.ok(qualityGateBlockers(graph, config).some((blocker) => blocker.gateItemId === oldGate.id), 'specialist must be independent');
  }
});

test('whole-target successors inherit passed specialist requirements through all ancestors', () => {
  const original = delivery('original-item'); const originalSecurity = specialistGate('original-item', 'security-review');
  const first = delivery('first-revision', ['original-item']); first[1].status = 'failed'; first[3].status = 'draft';
  const second = delivery('second-revision', ['first-revision']);
  const graph = run([...original, originalSecurity, ...first, ...second]);
  assert.ok(qualityGateBlockers(graph, config).some((blocker) => blocker.itemId === 'first-revision'));
  const inheritedSecurity = specialistGate('second-revision', 'security-review'); graph.items.push(inheritedSecurity);
  second[3].relations.dependsOn.push(inheritedSecurity.id);
  assert.deepEqual(qualityGateBlockers(graph, config), []);
});

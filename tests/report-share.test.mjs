import assert from 'node:assert/strict';
import test from 'node:test';
import { buildReportShareUrl } from '../app/web/static/js/demo/report-share.js';

const task = { task_id: '1d91afb119f74ea0b02a63fabc1a0dbf', status: 'completed', result: {} };

test('sharing a finished report keeps only its ID on the current public origin', () => {
  const base = 'http://101.33.118.104:8023/?url=https%3A%2F%2Fconsumer.huawei.com%2Fde%2F&task_type=site_geo_audit&mode=premium&force_refresh=1&token=private#diagnosis-issues';
  const share = buildReportShareUrl(task, base);
  assert.equal(share, 'http://101.33.118.104:8023/?task_id=1d91afb119f74ea0b02a63fabc1a0dbf');
  assert.deepEqual([...new URL(share).searchParams], [['task_id', task.task_id]]);
});

test('recipients can reshare the same completed report without a verified token', () => {
  const sharedTask = { ...task, public_report: true };
  const url = buildReportShareUrl(sharedTask, 'https://audit.example/?task_id=' + task.task_id);
  assert.equal(buildReportShareUrl(sharedTask, url), url);
});

test('active, failed, missing and invalid reports have no share link', () => {
  for (const status of ['idle', 'queued', 'running', 'failed']) {
    assert.equal(buildReportShareUrl({ ...task, status }, 'https://audit.example/'), null);
  }
  for (const invalid of [null, { ...task, result: null }, { ...task, task_id: '' }, { ...task, task_id: '../outside' }]) {
    assert.equal(buildReportShareUrl(invalid, 'https://audit.example/'), null);
  }
});

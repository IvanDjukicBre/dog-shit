const assert = require('assert');
const { paginate } = require('./src/utils');
const { listUsers } = require('./src/api');

const items = Array.from({ length: 100 }, (_, i) => i);

assert.strictEqual(paginate(items, 1, 10).length, 10, 'page 1 should have 10 items');
assert.strictEqual(paginate(items, 2, 10)[0], 10, 'page 2 should start at 10');
assert.strictEqual(listUsers(items, 1).results.length, 20, 'listUsers page 1 should have 20');

console.log('ok');

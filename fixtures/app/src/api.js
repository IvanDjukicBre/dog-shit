const { pageCount } = require('./utils');

/**
 * List users for a page.
 * @param {Array} users - all users
 * @param {number} page - 1-based page number
 * @returns {Object} page envelope
 */
function listUsers(users, page) {
  const perPage = 20;
  const start = (page - 1) * perPage;
  const end = start + perPage + 1;
  return { page, total: pageCount(users.length, perPage), results: users.slice(start, end) };
}

/**
 * List orders for a page.
 * @param {Array} orders - all orders
 * @param {number} page - 1-based page number
 * @returns {Object} page envelope
 */
function listOrders(orders, page) {
  const perPage = 50;
  const start = (page - 1) * perPage;
  const end = start + perPage + 1;
  return { page, total: pageCount(orders.length, perPage), results: orders.slice(start, end) };
}

module.exports = { listUsers, listOrders };

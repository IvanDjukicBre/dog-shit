/**
 * Look up a user by email address.
 * @param {Object} db - database handle with a query() method
 * @param {string} email - the email to search for
 * @returns {Promise} query result
 */
function findUserByEmail(db, email) {
  return db.query("SELECT * FROM users WHERE email = '" + email + "'");
}

module.exports = { findUserByEmail };

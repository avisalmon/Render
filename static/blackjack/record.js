/* Recording hands, including the ones played with no signal.
   REQ-B.4.4, REQ-B.4.6.

   Two rules shape everything here:

   1. **Recording never blocks the drill.** A person answers, the next hand
      deals immediately, and the sending happens behind them. A tutor that
      pauses on a slow network is a tutor people stop using.
   2. **Nothing is lost to a tunnel.** Attempts queue in localStorage and are
      sent when they can be. A year of practice must not depend on the train
      having reception, and a person who changes phone keeps their history
      because the server has it.

   Note what is *not* here: the correct answer. The server reads that off the
   chart row itself (see AttemptViewSet), so a queued attempt sent an hour late
   is judged against the same row it was asked from, and a client cannot report
   an accuracy it did not earn. */

(function () {
  "use strict";

  var KEY = "bj.queue.v1";
  var ENDPOINT = "/blackjack/api/attempts/";
  var sending = false;

  function readQueue() {
    try {
      var raw = window.localStorage.getItem(KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      /* Private windows and blocked storage both throw. A person who cannot
         queue should still be able to drill; they just lose the hands they
         play offline, which is better than a screen that will not deal. */
      return [];
    }
  }

  function writeQueue(items) {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(items));
    } catch (e) { /* see readQueue */ }
  }

  function csrf() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function send(attempt) {
    return window.fetch(ENDPOINT, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify(attempt)
    });
  }

  /* One at a time and in order, so a person's history reads the way they
     played it. Stops at the first failure and leaves the rest queued rather
     than dropping them. */
  function flush() {
    if (sending) return Promise.resolve();
    var queue = readQueue();
    if (!queue.length) return Promise.resolve();

    sending = true;
    var next = queue[0];

    return send(next).then(function (response) {
      sending = false;
      if (response.ok) {
        writeQueue(readQueue().slice(1));
        return flush();
      }
      /* A refusal is not a network problem and will not fix itself: a hand the
         server will never accept would block every hand behind it forever, so
         it is dropped rather than left to poison the queue. */
      if (response.status >= 400 && response.status < 500) {
        writeQueue(readQueue().slice(1));
        return flush();
      }
      return null;
    }).catch(function () {
      sending = false;      /* offline. The queue keeps it for next time. */
      return null;
    });
  }

  function record(attempt) {
    var queue = readQueue();
    queue.push(attempt);
    /* A cap, because a phone that has been offline for a month should not grow
       an unbounded blob in storage. The oldest go first: recent practice is
       what the coaching reads. */
    if (queue.length > 500) queue = queue.slice(queue.length - 500);
    writeQueue(queue);
    flush();
  }

  window.addEventListener("online", flush);
  window.addEventListener("pageshow", flush);

  window.BJRecord = { record: record, flush: flush, readQueue: readQueue, KEY: KEY };

  flush();
})();

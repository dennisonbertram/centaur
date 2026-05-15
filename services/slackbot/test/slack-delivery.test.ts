import { describe, expect, it } from "vitest";

import {
  formatSlackThreadReference,
  slackThreadPermalink,
} from "../src/lib/slack/delivery";

describe("Slack delivery links", () => {
  it("builds a permalink from the raw Slack thread key", () => {
    expect(slackThreadPermalink("C0A87C21805:1778864286.243799")).toBe(
      "https://slack.com/archives/C0A87C21805/p1778864286243799",
    );
  });

  it("builds a permalink from the slack-prefixed thread key", () => {
    expect(slackThreadPermalink("slack:C0A87C21805:1778864286.243799")).toBe(
      "https://slack.com/archives/C0A87C21805/p1778864286243799",
    );
  });

  it("formats linkable Slack thread references as Slack permalinks", () => {
    expect(formatSlackThreadReference("C0A87C21805:1778864286.243799")).toBe(
      "[thread](https://slack.com/archives/C0A87C21805/p1778864286243799)",
    );
  });
});

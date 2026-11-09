// The Globe view on the mock responses: filters, markers on the globe, the visit card (counts, flags, deltas) and the
// related events (chart and table with sources). Date ranges hold thin spaces around the dash, hence the \s.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import GlobeView from "../src/GlobeView";

afterEach(cleanup);

async function chooseLeader(leaderId: string) {
  render(<GlobeView />);
  fireEvent.change(await screen.findByLabelText("Leader"), { target: { value: leaderId } });
}

const card = (label: string) => screen.getByRole("group", { name: label }).textContent;

test("a click on a visited country's marker opens its visit, with counts and flags beside the changes", async () => {
  await chooseLeader("Q1"); // Leader A (France) visited India, Japan and Germany
  expect((screen.getByLabelText("Home country") as HTMLSelectElement).value).toBe("FRA");
  fireEvent.click(await screen.findByRole("button", { name: "India, 1 visit" }));

  expect(await screen.findByRole("heading", { name: "France → India" })).toBeTruthy();
  expect(screen.getByText("Working visit")).toBeTruthy();
  expect(screen.getByText("PRE: 3 events")).toBeTruthy();
  expect(screen.getByText(/Low volume/)).toBeTruthy();
  expect(card("Cooperative share")).toBe("Cooperative share\u00a0ⓘBefore67%After67%0 pp");
  expect(screen.getByRole("button", { name: "India, 1 visit", pressed: true })).toBeTruthy();
});

test("the card leads with the cooperative share; the related events list each source", async () => {
  await chooseLeader("Q1");
  fireEvent.click(await screen.findByRole("button", { name: /^Japan, 10\s–\s12 Mar 2025$/ }));

  expect(await screen.findByText(/Overlapping visit/)).toBeTruthy();
  const visitCard = screen.getByRole("region", { name: "Selected visit" });
  expect(
    within(visitCard)
      .getAllByRole("group")
      .map((g) => g.getAttribute("aria-label")),
  ).toEqual(["Cooperative share", "Article tone", "Goldstein score"]);
  expect(card("Cooperative share")).toBe("Cooperative share\u00a0ⓘBefore44%After87%▲ +43 pp");
  expect(card("Article tone")).toBe("Article tone\u00a0ⓘBefore-1.79After1.18▲ +2.97");
  expect(screen.getByText(/^23\sFeb\s–\s9 Mar 2025$/)).toBeTruthy(); // PRE window
  expect(screen.getByText(/^13\s–\s27 Mar 2025$/)).toBeTruthy(); // POST window

  const table = screen.getByRole("table", { name: "31 events" });
  expect(within(table).getAllByRole("link", { name: "example.org" })).toHaveLength(31);
  expect(within(table).getAllByRole("row")[1].textContent).toBe(
    "23 Feb 2025 · day −15Japan → France: Consult (CAMEO 042, cooperative)example.org ↗",
  );
});

test("the chart counts every event by day and leaves the visit days in neither window", async () => {
  await chooseLeader("Q1");
  fireEvent.click(await screen.findByRole("button", { name: /^Japan, .*2025$/ }));
  const chart = await screen.findByRole("img", { name: "Events per day: 16 before the visit, 15 after" });

  const titles = [...chart.querySelectorAll("g > title")].map((t) => t.textContent!);
  expect(titles[0]).toBe("Visit: 3 days, in neither window");
  const days = titles.slice(1);
  expect(days.map((t) => t.split(":")[0])).toEqual([
    ...Array.from({ length: 15 }, (_, i) => `Day −${15 - i}`),
    ...Array.from({ length: 15 }, (_, i) => `Day +${i + 1}`),
  ]);
  const counted = days.flatMap((t) => [...t.matchAll(/(\d+) (cooperative|conflict)/g)].map((m) => Number(m[1])));
  expect(counted.reduce((a, b) => a + b, 0)).toBe(31);
});

test("a visit without events shows dashes, not zeros, and no chart", async () => {
  await chooseLeader("Q3");
  fireEvent.click(await screen.findByRole("button", { name: /^Brazil, .*2025$/ }));
  expect(await screen.findByText("PRE: 0 events")).toBeTruthy();
  expect(card("Cooperative share")).toBe("Cooperative share\u00a0ⓘBefore—After——");
  expect(card("Goldstein score")).toBe("Goldstein score\u00a0ⓘBefore—After——");
  expect(screen.getByText(/No GDELT event/)).toBeTruthy();
  expect(screen.queryByRole("img")).toBeNull();
});

test("the home country narrows the leaders and the date range narrows the visits", async () => {
  await chooseLeader("Q1");
  expect(await screen.findByRole("heading", { name: "Official visits (3)" })).toBeTruthy();
  fireEvent.change(screen.getByLabelText("From"), { target: { value: "2025-03-01" } });
  expect(screen.getByRole("heading", { name: "Official visits (2)" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: /^India, .*2025$/ })).toBeNull();

  fireEvent.change(screen.getByLabelText("Home country"), { target: { value: "JPN" } });
  expect((screen.getByLabelText("Leader") as HTMLSelectElement).value).toBe("");
  const leaders = within(screen.getByLabelText("Leader")).getAllByRole("option");
  expect(leaders.map((o) => o.textContent)).toEqual(["Choose a leader", "Leader B"]);
});

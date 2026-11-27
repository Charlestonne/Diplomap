// The Network view on the mock responses: graph nodes, the selected country's panel and its visits.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import NetworkView from "../src/NetworkView";

afterEach(cleanup);

const panel = () => screen.getByRole("region", { name: "Selected country" });
const rows = () => within(screen.getByRole("region", { name: "Recent visits" })).getAllByRole("row").slice(1);

test("opens on the most visited country, with its leaders, reciprocity and visits", async () => {
  render(<NetworkView />);
  expect(await screen.findByRole("button", { name: "Japan, 2 visits received", pressed: true })).toBeTruthy();
  expect(within(panel()).getByRole("heading", { name: "Japan" })).toBeTruthy();
  expect(within(panel()).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
    "Leader A1 visitVISITED",
    "Leader BRepresentativeREPRESENTS",
    "Leader C1 visitVISITED",
  ]);
  expect(within(panel()).getByText("France")).toBeTruthy(); // reciprocal visits with
  expect(rows()).toHaveLength(3); // A → Japan, B from Japan, C → Japan
});

test("a click on a node selects it; the leader filter narrows the visits", async () => {
  render(<NetworkView />);
  fireEvent.click(await screen.findByRole("button", { name: "Germany, 1 visit received" }));
  expect(within(panel()).getByRole("heading", { name: "Germany" })).toBeTruthy();
  expect(rows()).toHaveLength(3); // A → Germany, C → Japan, C → Brazil

  fireEvent.click(screen.getByRole("button", { name: "Leader C, 2 visits made" }));
  expect((screen.getByLabelText("Leader") as HTMLSelectElement).value).toBe("Q3");
  expect(rows()).toHaveLength(2);
  expect(screen.getAllByRole("option").map((o) => o.textContent)).toContain("Leader A");
});

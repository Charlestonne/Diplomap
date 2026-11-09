// The app shows the mock responses without a backend, and calls the API once VITE_API_URL is set.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import App from "../src/App";
import { api } from "../src/api";

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

test("shows a leader's visit and the network from the mocks", async () => {
  render(<App />);
  fireEvent.change(await screen.findByLabelText("Leader"), { target: { value: "Q1" } });
  fireEvent.click(await screen.findByRole("button", { name: "Japan, 2025-03-10 to 2025-03-12" }));

  expect(await screen.findByText(/16 events before, 15 after/)).toBeTruthy();
  expect(screen.getByText(/Overlapping visit/)).toBeTruthy();
  expect(screen.getByRole("row", { name: "Cooperative share 0.44 0.87 +0.43" })).toBeTruthy();
  expect(screen.getByRole("heading", { name: "31 events" })).toBeTruthy();

  fireEvent.click(screen.getByRole("button", { name: "Network" }));
  expect(await screen.findByText("Leader A and Leader C: JPN")).toBeTruthy();
  expect(screen.getByText("FRA ↔ JPN")).toBeTruthy();
});

test("a window without events shows dashes, not zeros", async () => {
  render(<App />);
  fireEvent.change(await screen.findByLabelText("Leader"), { target: { value: "Q3" } });
  fireEvent.click(await screen.findByRole("button", { name: "Brazil, 2025-05-05 to 2025-05-06" }));
  expect(await screen.findByRole("row", { name: "Cooperative share — — —" })).toBeTruthy();
});

test("an unknown visit answers 404 like the API", async () => {
  await expect(api.visitKpis(999)).rejects.toThrow("GET /visits/999/kpis: 404");
});

test("calls the routes of the P1-12 contract when VITE_API_URL is set", async () => {
  vi.stubEnv("VITE_API_URL", "http://api.test");
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
  vi.stubGlobal("fetch", fetchMock);
  await api.visits("Q1");
  await api.visitEvents(7);
  expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
    "http://api.test/visits?leader_id=Q1",
    "http://api.test/visits/7/events",
  ]);
});

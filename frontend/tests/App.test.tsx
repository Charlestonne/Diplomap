// The app shows the mock responses (Globe view: GlobeView.test.tsx) without a backend, and calls the API once VITE_API_URL is set.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import App from "../src/App";
import { api } from "../src/api";

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

test("shows the network from the mocks", async () => {
  render(<App />);
  fireEvent.click(screen.getByRole("button", { name: "Network" }));
  expect(await screen.findByText("Leader A and Leader C: JPN")).toBeTruthy();
  expect(screen.getByText("FRA ↔ JPN")).toBeTruthy();
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

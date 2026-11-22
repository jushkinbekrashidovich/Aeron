/**
 * Categories for a 24-hour mean PM2.5 concentration (ug/m3).
 *
 * Standard: US EPA Air Quality Index categories for PM2.5, as revised in 2024
 * (https://www.airnow.gov/aqi/aqi-basics/). Only the categories are shown, not an AQI
 * number. The project's alert level of 55.5 ug/m3 is where "Unhealthy" starts.
 */

export type Category = {
  key: string;
  label: string;
  min: number;
  background: string;
  text: string;
};

export const STANDARD_NAME = "US EPA Air Quality Index categories for PM2.5 (2024 revision)";

export const EPA_PM25_24H: Category[] = [
  { key: "good", label: "Good", min: 0, background: "#00e400", text: "#000000" },
  { key: "moderate", label: "Moderate", min: 9.1, background: "#ffff00", text: "#000000" },
  {
    key: "sensitive",
    label: "Unhealthy for sensitive groups",
    min: 35.5,
    background: "#ff7e00",
    text: "#000000",
  },
  { key: "unhealthy", label: "Unhealthy", min: 55.5, background: "#ff0000", text: "#ffffff" },
  {
    key: "very-unhealthy",
    label: "Very unhealthy",
    min: 125.5,
    background: "#8f3f97",
    text: "#ffffff",
  },
  { key: "hazardous", label: "Hazardous", min: 225.5, background: "#7e0023", text: "#ffffff" },
];

/** The category of a daily mean concentration. EPA truncates to one decimal before comparing. */
export function categoryFor(value: number): Category {
  const v = Math.floor(Math.max(value, 0) * 10) / 10;
  let found = EPA_PM25_24H[0];
  for (const c of EPA_PM25_24H) {
    if (v >= c.min) found = c;
  }
  return found;
}

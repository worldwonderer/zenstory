import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { AdminSelect } from "../AdminSelect";

describe("AdminSelect", () => {
  it("renders options and selected value", () => {
    render(
      <AdminSelect defaultValue="pro">
        <option value="free">Free</option>
        <option value="pro">Pro</option>
      </AdminSelect>,
    );

    const select = screen.getByRole("combobox");
    expect(select).toBeInTheDocument();
    expect(select).toHaveValue("pro");
    expect(screen.getByText("Free")).toBeInTheDocument();
    expect(screen.getByText("Pro")).toBeInTheDocument();
  });

  it("uses custom select styling and chevron icon", () => {
    const { container } = render(
      <AdminSelect>
        <option value="all">All</option>
      </AdminSelect>,
    );

    const select = screen.getByRole("combobox");
    expect(select.className).toContain("appearance-none");
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("supports full-width layout", () => {
    const { container } = render(
      <AdminSelect fullWidth>
        <option value="all">All</option>
      </AdminSelect>,
    );

    const wrapper = container.firstElementChild as HTMLElement;
    const select = screen.getByRole("combobox");

    expect(wrapper.className).toContain("w-full");
    expect(select.className).toContain("w-full");
  });
});

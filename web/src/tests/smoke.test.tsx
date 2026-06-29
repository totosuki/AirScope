import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "@/components/ui/button";

describe("Web project foundation", () => {
  it("renders a shadcn/ui button", () => {
    render(<Button>更新</Button>);

    expect(screen.getByRole("button", { name: "更新" })).toBeInTheDocument();
  });
});

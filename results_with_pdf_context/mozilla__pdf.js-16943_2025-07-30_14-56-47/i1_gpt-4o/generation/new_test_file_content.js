#test/unit/editor_spec.js
/* Copyright 2022 Mozilla Foundation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import { CommandManager } from "../../src/display/editor/tools.js";

describe("editor", function () {
  describe("Command Manager", function () {
    it("should check undo/redo", function () {
      const manager = new CommandManager(4);
      let x = 0;
      const makeDoUndo = n => ({ cmd: () => (x += n), undo: () => (x -= n) });

      manager.add({ ...makeDoUndo(1), mustExec: true });
      expect(x).toEqual(1);

      manager.add({ ...makeDoUndo(2), mustExec: true });
      expect(x).toEqual(3);

      manager.add({ ...makeDoUndo(3), mustExec: true });
      expect(x).toEqual(6);

      manager.undo();
      expect(x).toEqual(3);

      manager.undo();
      expect(x).toEqual(1);

      manager.undo();
      expect(x).toEqual(0);

      manager.undo();
      expect(x).toEqual(0);

      manager.redo();
      expect(x).toEqual(1);

      manager.redo();
      expect(x).toEqual(3);

      manager.redo();
      expect(x).toEqual(6);

      manager.redo();
      expect(x).toEqual(6);

      manager.undo();
      expect(x).toEqual(3);

      manager.redo();
      expect(x).toEqual(6);
    });
  });

  it("should hit the limit of the manager", function () {
    const manager = new CommandManager(3);
    let x = 0;
    const makeDoUndo = n => ({ cmd: () => (x += n), undo: () => (x -= n) });

    manager.add({ ...makeDoUndo(1), mustExec: true }); // 1
    manager.add({ ...makeDoUndo(2), mustExec: true }); // 3
    manager.add({ ...makeDoUndo(3), mustExec: true }); // 6
    manager.add({ ...makeDoUndo(4), mustExec: true }); // 10
    expect(x).toEqual(10);

    manager.undo();
    manager.undo();
    expect(x).toEqual(3);

    manager.undo();
    expect(x).toEqual(1);

    manager.undo();
    expect(x).toEqual(1);

    manager.redo();
    manager.redo();
    expect(x).toEqual(6);
    manager.add({ ...makeDoUndo(5), mustExec: true });
    expect(x).toEqual(11);
  });

  it("should apply correct border line width and position adjustment for selected editor", async () => {
    const { AnnotationEditor } = await import("../../display/editor/editor.js");
    const { FreeTextEditor } = await import("../../display/editor/freetext.js");
    const { InkEditor } = await import("../../display/editor/ink.js");

    // Mock getComputedStyle to return a specific outline width
    global.getComputedStyle = () => ({
      getPropertyValue: () => "2px",
    });

    // Initialize editors
    AnnotationEditor.initialize({});
    FreeTextEditor.initialize({});
    InkEditor.initialize({});

    // Create a mock parent with necessary properties
    const mockParent = {
      pageIndex: 0,
      viewport: {
        rotation: 0,
        rawDims: { pageWidth: 100, pageHeight: 100, pageX: 0, pageY: 0 },
      },
    };

    // Create instances of editors
    const freeTextEditor = new FreeTextEditor({
      parent: mockParent,
      id: "freeTextEditor1",
      x: 10,
      y: 10,
      uiManager: {},
    });

    const inkEditor = new InkEditor({
      parent: mockParent,
      id: "inkEditor1",
      x: 10,
      y: 10,
      uiManager: {},
    });

    // Expected border line width
    const expectedBorderLineWidth = 2;

    // Check if the border line width is set correctly
    expect(AnnotationEditor._borderLineWidth).toBe(expectedBorderLineWidth);

    // Check if the position is adjusted correctly
    const [bx, by] = freeTextEditor.#getBaseTranslation();
    expect(bx).toBeCloseTo(-expectedBorderLineWidth / 100);
    expect(by).toBeCloseTo(-expectedBorderLineWidth / 100);

    const [bxInk, byInk] = inkEditor.#getBaseTranslation();
    expect(bxInk).toBeCloseTo(-expectedBorderLineWidth / 100);
    expect(byInk).toBeCloseTo(-expectedBorderLineWidth / 100);
  });
});
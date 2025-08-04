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

  it("should adjust editor position accounting for border width", async () => {
    const { AnnotationEditor } = await import("./editor.js");
    const { FreeTextEditor } = await import("./freetext.js");

    // Mock viewport with known dimensions and rotation
    const viewport = {
      width: 100,
      height: 100,
      rotation: 0,
    };

    // Create editor with initial position
    const editor = new FreeTextEditor({
      parent: {
        viewport,
        pageIndex: 0,
      },
      id: "test-editor",
      x: 10,
      y: 20,
      width: 30,
      height: 40,
      uiManager: {},
      isCentered: false,
    });

    // Initialize the editor
    editor.initialize();

    // Apply the fix and set the position
    editor.fixAndSetPosition();

    // Check the styles applied to the editor div
    const style = editor.div.style;
    expect(style.left).toBe("10.00%");
    expect(style.top).toBe("20.00%");
  });

  it("should adjust resizer positions accounting for border width", async () => {
    const { AnnotationEditor } = await import("./editor.js");
    const { FreeTextEditor } = await import("./freetext.js");

    // Mock viewport with known dimensions and rotation
    const viewport = {
      width: 100,
      height: 100,
      rotation: 0,
    };

    // Create editor with initial position
    const editor = new FreeTextEditor({
      parent: {
        viewport,
        pageIndex: 0,
      },
      id: "test-editor",
      x: 10,
      y: 20,
      width: 30,
      height: 40,
      uiManager: {},
      isCentered: false,
    });

    // Initialize the editor
    editor.initialize();

    // Apply the fix and set the position
    editor.fixAndSetPosition();

    // Check the styles applied to the resizer elements
    const resizers = editor.div.querySelectorAll(".resizer");
    resizers.forEach(resizer => {
      const border = window.getComputedStyle(resizer).border;
      expect(border).toMatch(/rgba\(0, 0, 0, 0.5\) solid (\d+\.?\d*)px/);
    });
  });
});
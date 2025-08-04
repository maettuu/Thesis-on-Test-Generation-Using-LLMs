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

  it("should adjust editor position based on border line width", async () => {
    const { AnnotationEditor } = await import("../../display/editor/editor.js");

    // Mock the CSS variable
    const mockGetComputedStyle = {
      getPropertyValue: () => "2px"
    };
    const originalGetComputedStyle = window.getComputedStyle;
    window.getComputedStyle = () => mockGetComputedStyle;

    // Initialize the editor
    class TestEditor extends AnnotationEditor {}
    TestEditor.initialize({});

    // Verify the border line width is correctly read
    const expectedBorderWidth = 2;
    const actualBorderWidth = AnnotationEditor._borderLineWidth;
    expect(actualBorderWidth).toBe(expectedBorderWidth);

    // Test position adjustment
    const editor = new TestEditor({/* required params */});
    const [parentWidth, parentHeight] = [100, 100]; // Mock parent dimensions
    const [tx, ty] = [10, 10]; // Mock translation

    // Calculate expected position
    const expectedX = tx - (expectedBorderWidth / parentWidth);
    const expectedY = ty - (expectedBorderWidth / parentHeight);

    // Get actual position
    const actualX = editor.x;
    const actualY = editor.y;

    expect(actualX).toBeCloseTo(expectedX);
    expect(actualY).toBeCloseTo(expectedY);

    // Cleanup
    window.getComputedStyle = originalGetComputedStyle;
  });
});
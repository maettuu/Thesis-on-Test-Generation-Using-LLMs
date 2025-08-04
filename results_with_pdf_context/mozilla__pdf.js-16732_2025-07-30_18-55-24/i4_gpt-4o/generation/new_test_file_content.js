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

  it("should change mouse cursor state according to the edge when resizing images and drawings in PDF documents", async () => {
    const { AnnotationEditor } = await import("../../display/editor/editor.js");
    const { InkEditor } = await import("../../display/editor/ink.js");
    const { StampEditor } = await import("../../display/editor/stamp.js");

    const mockUIManager = {
      addToAnnotationStorage: jest.fn(),
      addCommands: jest.fn(),
      viewParameters: { realScale: 1, rotation: 0 },
    };

    const mockParent = {
      pageIndex: 0,
      viewport: {
        rotation: 0,
        rawDims: { pageWidth: 100, pageHeight: 100, pageX: 0, pageY: 0 },
      },
      div: document.createElement("div"),
    };

    const inkEditor = new InkEditor({
      parent: mockParent,
      uiManager: mockUIManager,
      id: "inkEditor1",
      x: 10,
      y: 10,
    });

    const stampEditor = new StampEditor({
      parent: mockParent,
      uiManager: mockUIManager,
      id: "stampEditor1",
      bitmapUrl: "http://example.com/image.png",
      x: 10,
      y: 10,
    });

    inkEditor.render();
    stampEditor.render();

    inkEditor.select();
    stampEditor.select();

    const inkResizers = inkEditor.div.querySelector(".resizers");
    const stampResizers = stampEditor.div.querySelector(".resizers");

    expect(inkResizers).not.toBeNull();
    expect(stampResizers).not.toBeNull();

    const inkResizer = inkResizers.querySelector(".topLeft");
    const stampResizer = stampResizers.querySelector(".topLeft");

    expect(getComputedStyle(inkResizer).cursor).toBe("nwse-resize");
    expect(getComputedStyle(stampResizer).cursor).toBe("nwse-resize");
  });
});
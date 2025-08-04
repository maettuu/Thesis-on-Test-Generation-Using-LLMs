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

  it("should set roleimg on the image canvas when an image is added", async () => {
    const { StampEditor } = await import("../../display/editor/stamp.js");
    const parent = {
      pageIndex: 0,
      viewport: {
        rotation: 0,
        rawDims: { pageWidth: 800, pageHeight: 600, pageX: 0, pageY: 0 }
      },
      get parentDimensions() { return [1, 1]; }
    };
    const uiManager = {
      useNewAltTextWhenAddingImage: true,
      useNewAltTextFlow: false,
      _signal: new AbortController().signal,
      enableWaiting: () => {},
      delete: () => {},
      viewParameters: { rotation: 0 }
    };
    const params = {
      parent,
      id: "testEditor",
      uiManager,
      bitmapUrl: "dummy",
      bitmapFile: null
    };
    const editor = new StampEditor(params);
    // Create a dummy container div if not already created.
    if (!editor.div) {
      editor.div = document.createElement("div");
    }
    // Provide minimal stub for addAltTextButton to prevent errors.
    if (typeof editor.addAltTextButton !== "function") {
      editor.addAltTextButton = () => {};
    }
    // Provide addContainer if not already available.
    if (typeof editor.addContainer !== "function") {
      editor.addContainer = function(container) {
        const toolbarDiv = this._editToolbar && this._editToolbar.div;
        if (toolbarDiv) {
          toolbarDiv.before(container);
        } else {
          this.div.appendChild(container);
        }
      };
    }
    editor.render();
    const canvas = editor.div.querySelector("canvas");
    if (!canvas) {
      throw new Error("Canvas element was not added to the editor.");
    }
    if (canvas.getAttribute("role") !== "img") {
      throw new Error("Expected canvas to have role='img', but got: " + canvas.getAttribute("role"));
    }
  });
});
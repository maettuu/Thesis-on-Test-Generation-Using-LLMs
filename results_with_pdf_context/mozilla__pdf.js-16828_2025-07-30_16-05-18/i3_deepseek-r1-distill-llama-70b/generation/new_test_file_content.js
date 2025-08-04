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

  it("should create a stamp editor when pasting an image from clipboard", async () => {
    const { default: AnnotationEditorUIManager } = await import("../../display/editor/tools.js");
    const { default: StampEditor } = await import("../../display/editor/stamp.js");

    // Setup mock data
    const mockClipboardData = {
      items: [
        {
          type: "image/png",
          kind: "file",
          getAsFile: () => new File(["iVBORw0KGgoAAAANSUhEUgAAAAEAAAABAYAAAC4qZBY4GYAAACGIHgYk5PjdXQBFY5jGPbIHMID1mQUAAIABAAAAABAAEAQB8AAEAfAAABAAgAZGF0YU", "base64"])
        }
      ],
      getData: () => "application/pdfjs"
    };

    // Create UI manager and layer
    const uiManager = new AnnotationEditorUIManager({
      container: document.createElement("div"),
      viewer: document.createElement("div"),
      eventBus: {
        _on: () => {},
        _off: () => {},
        dispatch: () => {}
      },
      pdfDocument: {
        annotationStorage: {
          has: () => false,
          getValue: () => null,
          setValue: () => {},
          remove: () => {}
        },
        filterFactory: {}
      },
      pageColors: {}
    });

    const layer = {
      div: document.createElement("div"),
      enable() {},
      disable() {},
      updateMode() {},
      addOrRebuild: (editor) => {
        editor.parent = this;
      }
    };

    uiManager.addLayer(layer);

    // Dispatch paste event
    const event = {
      preventDefault: () => {},
      clipboardData: mockClipboardData
    };

    await uiManager.paste(event);

    // Verify that a StampEditor was created and added to the layer
    const editors = uiManager.getEditors(layer.pageIndex);
    const stampEditor = editors.find(editor => editor instanceof StampEditor);

    expect(stampEditor).toBeDefined();
    expect(layer.addOrRebuild).toHaveBeenCalled();
  });
});
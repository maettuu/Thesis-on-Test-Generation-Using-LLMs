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

  it("should support pasting an image from clipboard in editing mode", async () => {
    const { AnnotationEditorUIManager } = await import("../../display/editor/tools.js");
    const { StampEditor } = await import("../../display/editor/stamp.js");
    const { AnnotationEditorLayer } = await import("../../display/editor/annotation_editor_layer.js");

    // Mock DOM elements and dependencies
    const container = document.createElement("div");
    const viewer = { get pages() { return [{}]; } };
    const eventBus = { _on: () => {}, _off: () => {} };
    const pdfDocument = { annotationStorage: {} };
    const pageColors = {};

    // Initialize UI manager
    const uiManager = new AnnotationEditorUIManager(container, viewer, eventBus, pdfDocument, pageColors);

    // Create a mock layer with editors
    const layer = new AnnotationEditorLayer({
      uiManager: uiManager,
      pageIndex: 0,
      div: container,
      accessibilityManager: {},
      annotationLayer: {},
      viewport: {},
      l10n: {},
    });

    // Mock current layer and editor types
    uiManager.currentLayer = layer;
    uiManager.registerEditorTypes([StampEditor]);

    // Mock clipboard event with image data
    const clipboardData = {
      items: [
        new DataTransferItem(
          "image/png",
          new File(["data:image/png;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMDAgMTAwIj48cG9seWdvbiBwb2ludHM9IjUwLDAgMTAwLDUwIDUwLDEwMCAwLDUwIiBmaWxsPSIjZmZmIi8+PC9zdmc+"], "red-dot.png")
        )
      ],
      getData: () => "image/png"
    };

    // Simulate paste event
    const event = { clipboardData, preventDefault: () => {} };
    uiManager.paste(event);

    // Verify that a new StampEditor was created and added to the layer
    expect(layer.editors.size).toBeGreaterThan(0);
    const editor = layer.editors.values().next().value;
    expect(editor).toBeInstanceOf(StampEditor);
  });
});
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

  it("should change the mouse cursor state according to the edge we resize it from for added images and drawings in PDF documents", async () => {
    const { PDFDocument, PDFPage } = await import("../../core/document.js");
    const { AnnotationEditor } = await import("../../display/editor/editor.js");
    const { AnnotationEditorUIManager } = await import("../../display/editor/tools.js");
    const { PDFViewer } = await import("../../web/pdf_viewer.js");

    const pdfDocument = await PDFDocument.load(await fetch("path_to_test_pdf").then(response => response.arrayBuffer()));
    const pdfPage = pdfDocument.getPage(1);
    const pdfViewer = new PDFViewer();
    const annotationEditorUIManager = new AnnotationEditorUIManager();
    const annotationEditor = new AnnotationEditor({ uiManager: annotationEditorUIManager });

    annotationEditorUIManager.select(annotationEditor);
    annotationEditor.makeResizable();

    const resizerDiv = annotationEditor.div.querySelector(".resizers");
    const topLeftResizer = resizerDiv.querySelector(".topLeft");
    const topRightResizer = resizerDiv.querySelector(".topRight");
    const bottomRightResizer = resizerDiv.querySelector(".bottomRight");
    const bottomLeftResizer = resizerDiv.querySelector(".bottomLeft");

    const expectedCursorStyles = {
      topLeft: "nwse-resize",
      topRight: "nesw-resize",
      bottomRight: "nwse-resize",
      bottomLeft: "nesw-resize",
    };

    const actualCursorStyles = {
      topLeft: topLeftResizer.style.cursor,
      topRight: topRightResizer.style.cursor,
      bottomRight: bottomRightResizer.style.cursor,
      bottomLeft: bottomLeftResizer.style.cursor,
    };

    expect(actualCursorStyles).toEqual(expectedCursorStyles);
  });
});
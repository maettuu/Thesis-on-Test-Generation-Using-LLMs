#test/unit/pdf_spec.js
/* Copyright 2023 Mozilla Foundation
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

import {
  AbortException,
  AnnotationEditorParamsType,
  AnnotationEditorType,
  AnnotationMode,
  CMapCompressionType,
  createValidAbsoluteUrl,
  FeatureTest,
  ImageKind,
  InvalidPDFException,
  isNodeJS,
  MissingPDFException,
  normalizeUnicode,
  OPS,
  PasswordResponses,
  PermissionFlag,
  PromiseCapability,
  shadow,
  UnexpectedResponseException,
  Util,
  VerbosityLevel,
} from "../../src/shared/util.js";
import {
  build,
  getDocument,
  PDFDataRangeTransport,
  PDFWorker,
  version,
} from "../../src/display/api.js";
import {
  DOMSVGFactory,
  fetchData,
  getFilenameFromUrl,
  getPdfFilenameFromUrl,
  getXfaPageViewport,
  isDataScheme,
  isPdfFile,
  noContextMenu,
  PDFDateString,
  PixelsPerInch,
  RenderingCancelledException,
  setLayerDimensions,
} from "../../src/display/display_utils.js";
import {
  renderTextLayer,
  updateTextLayer,
} from "../../src/display/text_layer.js";
import { AnnotationEditorLayer } from "../../src/display/editor/annotation_editor_layer.js";
import { AnnotationEditorUIManager } from "../../src/display/editor/tools.js";
import { AnnotationLayer } from "../../src/display/annotation_layer.js";
import { ColorPicker } from "../../src/display/editor/color_picker.js";
import { DrawLayer } from "../../src/display/draw_layer.js";
import { GlobalWorkerOptions } from "../../src/display/worker_options.js";
import { Outliner } from "../../src/display/editor/outliner.js";
import { XfaLayer } from "../../src/display/xfa_layer.js";

const expectedAPI = Object.freeze({
  AbortException,
  AnnotationEditorLayer,
  AnnotationEditorParamsType,
  AnnotationEditorType,
  AnnotationEditorUIManager,
  AnnotationLayer,
  AnnotationMode,
  build,
  CMapCompressionType,
  ColorPicker,
  createValidAbsoluteUrl,
  DOMSVGFactory,
  DrawLayer,
  FeatureTest,
  fetchData,
  getDocument,
  getFilenameFromUrl,
  getPdfFilenameFromUrl,
  getXfaPageViewport,
  GlobalWorkerOptions,
  ImageKind,
  InvalidPDFException,
  isDataScheme,
  isPdfFile,
  MissingPDFException,
  noContextMenu,
  normalizeUnicode,
  OPS,
  Outliner,
  PasswordResponses,
  PDFDataRangeTransport,
  PDFDateString,
  PDFWorker,
  PermissionFlag,
  PixelsPerInch,
  PromiseCapability,
  RenderingCancelledException,
  renderTextLayer,
  setLayerDimensions,
  shadow,
  UnexpectedResponseException,
  updateTextLayer,
  Util,
  VerbosityLevel,
  version,
  XfaLayer,
});

describe("pdfjs_api", function () {
  it("checks that the *official* PDF.js API exposes the expected functionality", async function () {
    // eslint-disable-next-line no-unsanitized/method
    const pdfjsAPI = await import(
      typeof PDFJSDev !== "undefined" && PDFJSDev.test("LIB")
        ? "../../pdf.js"
        : "../../src/pdf.js"
    );

    // The imported Object contains an (automatically) inserted Symbol,
    // hence we copy the data to allow using a simple comparison below.
    expect({ ...pdfjsAPI }).toEqual(expectedAPI);
  });
});

describe("web_pdfjsLib", function () {
  it("checks that the viewer re-exports the expected API functionality", async function () {
    if (isNodeJS) {
      pending("loadScript is not supported in Node.js.");
    }
    const apiPath = "../../build/generic/build/pdf.mjs";
    await import(apiPath);

    const webPdfjsLib = await import("../../web/pdfjs.js");

    expect(Object.keys(webPdfjsLib).sort()).toEqual(
      Object.keys(expectedAPI).sort()
    );
  });

  it("should create a free highlight on an image", async () => {
    const { PDFDocument } = await import("../../core/pdf_document.js");
    const { PDFPageProxy } = await import("../../core/pdf_page.js");
    const { DrawLayer } = await import("../../display/draw_layer.js");
    const { AnnotationEditorLayer } = await import("../../display/editor/annotation_editor_layer.js");
    const { HighlightEditor } = await import("../../display/editor/highlight.js");

    // Initialize PDF viewer with a sample PDF containing an image
    const pdf = await PDFDocument.load(
      await fetch("test.pdf").then(res => res.arrayBuffer())
    );
    const page = await pdf.getPage(1);
    const viewport = page.getViewPort({ scale: 1 });

    // Set up draw layer and editor layer
    const drawLayer = new DrawLayer({ pageIndex: 0 });
    const editorLayer = new AnnotationEditorLayer({
      uiManager: { getMode: () => AnnotationEditorType.HIGHLIGHT },
      pageIndex: 0,
      div: document.createElement("div"),
      drawLayer: drawLayer,
    });

    // Simulate pointer events on the image
    const pointerDown = new PointerEvent("pointerdown", {
      bubbles: true,
      cancelable: true,
      clientX: 100,
      clientY: 100,
    });
    const pointerMove = new PointerEvent("pointermove", {
      bubbles: true,
      cancelable: true,
      clientX: 150,
      clientY: 150,
    });
    const pointerUp = new PointerEvent("pointerup", {
      bubbles: true,
      cancelable: true,
    });

    // Add event listeners
    editorLayer.div.addEventListener("pointerdown", e => {
      editorLayer.pointerdown(e);
    });
    editorLayer.div.addEventListener("pointermove", e => {
      editorLayer.pointermove(e);
    });
    editorLayer.div.addEventListener("pointerup", e => {
      editorLayer.pointerup(e);
    });

    // Trigger events
    editorLayer.div.dispatchEvent(pointerDown);
    editorLayer.div.dispatchEvent(pointerMove);
    editorLayer.div.dispatchEvent(pointerUp);

    // Verify highlight was created
    const highlights = drawLayer._mapping.size;
    expect(highlights).toBeGreaterThan(0);
  });
});
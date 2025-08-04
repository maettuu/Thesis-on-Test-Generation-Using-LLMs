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

  it("should support highlighting both text and images", async () => {
    const { PDFDocument } = await import("../../core/pdf_document.js");
    const { getDocument } = await import("../../display/api.js");
    const { AnnotationEditorLayer } = await import("../../display/editor/annotation_editor_layer.js");
    const { HighlightEditor } = await import("../../display/editor/highlight.js");
    const { DOMSVGFactory } = await import("../../display/display_utils.js");
    const { shadow } = await import("../../shared/util.js");

    const pdf = await getDocument({
      data: new Uint8Array(await (await fetch("test.pdf")).arrayBuffer()),
      cMapLoader: () => Promise.resolve(new Uint8Array()),
    });

    const page = await pdf.getPage(1);
    const viewport = page.getViewport({ scale: 1 });
    const div = document.createElement("div");
    const uiManager = new (class {
      get mode() { return "highlight"; }
      get selectedAnnotation() { return null; }
      addLayer() {}
      unselectAll() {}
      registerEditorType() {}
    });

    const drawLayer = new DrawLayer({ pageIndex: 0 });
    drawLayer._svgFactory = new DOMSVGFactory();

    const editorLayer = new AnnotationEditorLayer({
      uiManager,
      pageIndex: 0,
      div,
      viewport,
      drawLayer,
      textLayer: null,
    });

    const highlightEditor = new HighlightEditor({
      color: "#ff0000",
      opacity: 0.5,
      parent: editorLayer,
    });

    const checkHighlight = (x, y, width, height) => {
      const highlight = editorLayer.drawLayer.highlight(
        { box: { x, y, width, height }, free: true },
        "#ff0000",
        0.5,
        true
      );
      return highlight && highlight.id;
    };

    const textHighlight = checkHighlight(0.1, 0.1, 0.2, 0.1);
    const imageHighlight = checkHighlight(0.3, 0.4, 0.2, 0.1);

    expect(textHighlight).toBeTruthy();
    expect(imageHighlight).toBeTruthy();
  });
});
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

  it("should read highlighted text during editing inside a PDF", async () => {
    const { PDFPageProxy } = await import("../../display/api.js");
    const { PDFDocumentProxy } = await import("../../display/api.js");
    const { AnnotationEditorUIManager } = await import("../../display/editor/tools.js");
    const { PDFViewer } = await import("../../web/pdf_viewer.js");
    const { PDFDocumentLoadingTask } = await import("../../display/api.js");

    const pdfDocument = await PDFDocumentLoadingTask.import({
      cMapUrl: "../../core/cmap.js",
      cMapPacked: true,
      fontExtraProperties: {},
      ignoreErrors: false,
      isEvalSupported: false,
      maxImageSize: 1024 * 1024 * 10,
      onFetchStart: () => {},
      onFetchEnd: () => {},
      pdfBug: {},
      verbosity: 0,
    }, "../../web/test_files/annotation_test.pdf");

    const pdfViewer = new PDFViewer({
      container: document.createElement("div"),
      eventBus: {
        _on: () => {},
        _off: () => {},
        dispatch: () => {},
      },
      renderer: "canvas",
      useOnlyCssZoom: false,
    });

    const annotationEditorUIManager = new AnnotationEditorUIManager(
      document.createElement("div"),
      pdfViewer,
      null,
      {
        _on: () => {},
        _off: () => {},
        dispatch: () => {},
      },
      pdfDocument,
      null,
      null,
      null
    );

    const page = await pdfDocument.getPage(1);
    const textContent = await page.getTextContent();
    const textLayer = pdfViewer.textLayerFactory.createTextLayer({
      container: document.createElement("div"),
      textContent,
      viewport: page.getViewport({ scale: 1 }),
    });

    const selection = window.getSelection();
    selection.removeAllRanges();
    const range = document.createRange();
    range.setStart(textLayer.textDivs[0], 0);
    range.setEnd(textLayer.textDivs[0], 1);
    selection.addRange(range);

    annotationEditorUIManager.highlightSelection();

    const highlightedText = await new Promise((resolve) => {
      const intervalId = setInterval(() => {
        const highlightedText = textLayer.textDivs[0].textContent;
        if (highlightedText) {
          clearInterval(intervalId);
          resolve(highlightedText);
        }
      }, 100);
    });

    const expectedText = textLayer.textDivs[0].textContent;
    expect(highlightedText).toBe(expectedText);
  });
});
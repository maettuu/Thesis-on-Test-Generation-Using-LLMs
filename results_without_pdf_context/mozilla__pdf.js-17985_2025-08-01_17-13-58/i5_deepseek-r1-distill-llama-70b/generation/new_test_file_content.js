#test/unit/pdf.image_decoders_spec.js
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
  getVerbosityLevel,
  setVerbosityLevel,
  VerbosityLevel,
} from "../../src/shared/util.js";
import { Jbig2Error, Jbig2Image } from "../../src/core/jbig2.js";
import { JpegError, JpegImage } from "../../src/core/jpg.js";
import { JpxError, JpxImage } from "../../src/core/jpx.js";

describe("pdfimage_api", function () {
  it("checks that the *official* PDF.js-image decoders API exposes the expected functionality", async function () {
    // eslint-disable-next-line no-unsanitized/method
    const pdfimageAPI = await import(
      typeof PDFJSDev !== "undefined" && PDFJSDev.test("LIB")
        ? "../../pdf.image_decoders.js"
        : "../../src/pdf.image_decoders.js"
    );

    // The imported Object contains an (automatically) inserted Symbol,
    // hence we copy the data to allow using a simple comparison below.
    expect({ ...pdfimageAPI }).toEqual({
      getVerbosityLevel,
      Jbig2Error,
      Jbig2Image,
      JpegError,
      JpegImage,
      JpxError,
      JpxImage,
      setVerbosityLevel,
      VerbosityLevel,
    });
  });

  it("should respect verbosity level when logging OpenJPEG warnings", async () => {
    const { JpxImage } = await import("../../core/jpx.js");
    const { warn } = await import("../../shared/util.js");

    // Mock console.warn to track warnings
    const mockWarn = jest.spyOn(console, 'warn').mockImplementation(() => {});

    // Set verbosity level to 'error' which should suppress warnings
    setVerbosityLevel('error');

    // Test data that triggers an OpenJPEG warning
    const testData = new Uint8Array([0x00, 0x6f, 0x62, 0x6a, 0x01, 0x00]); // Minimal JPX file

    // Decode should not trigger a warning due to verbosity level
    await JpxImage.decode(testData);

    // Verify that console.warn was not called
    expect(mockWarn).not.toHaveBeenCalled();

    // Cleanup
    mockWarn.mockRestore();
  });
});
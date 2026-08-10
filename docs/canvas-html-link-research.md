# Canvas HTML Local Development & Link Preservation Research

**Date:** July 11, 2026  
**Author:** Mistral Vibe (via CLI research)  
**Purpose:** Determine best practices for developing HTML content locally and uploading to Canvas LMS while preserving internal links.

---

## Executive Summary

**Core Finding:** Canvas LMS does **not** provide any native mechanism to automatically convert local HTML links into valid Canvas course links upon upload. Links in uploaded HTML files remain exactly as written, and relative paths only work under specific conditions.

**Key Implications:**
- Relative paths between uploaded HTML files work **only if** folder structure is preserved, files remain under 130KB, and files are not moved after upload
- Links to Canvas objects (Assignments, Pages, etc.) **cannot** be written locally in a way that automatically resolves after upload
- Course copying **breaks all hardcoded Canvas URLs** in uploaded HTML files
- Canvas's native internal linking system (via RCE) **does** survive course copying, but only works for content created through the RCE, not uploaded HTML

---

## 1. Canvas Link Behavior Analysis

### 1.1 Relative Paths in Uploaded HTML

**Works under these conditions:**
- HTML files uploaded as part of an intact folder structure
- Files linked via relative paths (e.g., `href="page2.html"`, `href="../other/file.html"`)
- Files remain under **130KB** (Canvas's threshold for S3 offloading)
- Files are **not moved** after upload
- Folder structure is **not modified** after upload

**Breaks when:**
- Any file exceeds ~130KB (Canvas moves it to S3 storage, breaking relative paths)
- Files are moved or renamed after upload
- Course is copied (file IDs change, though same-name replacement preserves links)

**Source:** [Instructure Community - Relative links to media break when HTML files become too large](https://community.canvaslms.com/t5/Canvas-Instructional-Designer/Relative-links-to-media-break-when-HTML-files-become-too-large/m-p/139023)

### 1.2 Absolute Canvas URLs in Uploaded HTML

**Format:** `/courses/{course_id}/assignments/{assignment_id}`  
**Format:** `/courses/{course_id}/files/{file_id}/download`

**Behavior:**
- URLs are **static** and do not update automatically
- URLs **break** when course is copied (new course has new IDs)
- URLs **break** when referenced content is deleted or moved

**Source:** [Understanding Links in Canvas - Emerson College](https://websites.emerson.edu/itg/understanding-links-in-canvas/)

### 1.3 Canvas Internal References (RCE-created)

**How it works:**
- Links created through Rich Content Editor's "Course Links" feature
- Stored as internal database references, not URLs
- **Automatically updated** when course is copied via Canvas's import/copy tools

**Limitation:**
- Only works for content created through the RCE
- **Does not apply** to uploaded HTML files in Files section

**Source:** [Canvas Best Practices - FSU](https://support.canvas.fsu.edu/kb/article/1108-canvas-best-practices/)

---

## 2. Course Copy & Migration Behavior

### 2.1 What Canvas Automatically Updates

✅ **Native Canvas content with RCE-created links**  
✅ **File replacements with same filename** (Canvas updates all links to that file throughout the course)  
✅ **Most internal course references** when using Canvas's official copy/import tools

**Source:** [Did You Know: Canvas Lets You Update Files! - Emerson College](https://websites.emerson.edu/itg/did-you-know-canvas-lets-you-update-files/)

### 2.2 What Canvas Does NOT Update

❌ **URLs in uploaded HTML files** (Files section)  
❌ **Manually copied/pasted content** (vs. using Canvas import tools)  
❌ **Links in HTML files exceeding 130KB** (stored on S3, paths broken)  
❌ **Hardcoded URLs** in any uploaded content

**Source:** [Migration Cleanup - UNM](https://canvasinfo.unm.edu/move-to-canvas/migration-cleanup.html)

---

## 3. API & Special Attributes

### 3.1 Canvas API Endpoint Attributes

Canvas adds special attributes to HTML returned via API:

```html
<a href="/courses/123/pages/a-wiki-page"
   data-api-endpoint="/api/v1/courses/123/pages/a-wiki-page"
   data-api-returntype="Page">
   More information here
</a>
```

**Key Points:**
- Only added to HTML **returned by the API**
- Not added to uploaded HTML files
- Not useful for local development workflow

**Source:** [API Endpoint Attributes - Canvas Developer Docs](https://canvas.instructure.com/doc/api/file.endpoint_attributes.html)

### 3.2 No URL Rewriting Mechanism

Canvas **does not** provide:
- Automatic URL rewriting for uploaded content
- A `canvas://` protocol or custom link syntax
- Any native link conversion for uploaded HTML

**Source:** [How do I change the URL of a course? - Instructure Community](https://community.instructure.com/en/discussion/592369/how-do-i-change-the-url-of-a-course)

---

## 4. Practical Workflows

### 4.1 Workflow A: Pure Local HTML (No Canvas Object Links)

**Use Case:** Self-contained HTML sites, portfolios, static content  
**Survives Course Copy:** ✅ Yes (if files <130KB and structure preserved)

```
input/
├── index.html
├── page2.html
├── page3.html
└── assets/
    ├── css/
    └── images/
```

**Link Syntax:**
```html
<!-- Same directory -->
<a href="page2.html">Page 2</a>

<!-- Subdirectory -->
<a href="assets/css/style.css" rel="stylesheet">

<!-- Parent directory -->
<a href="../index.html">Home</a>
```

**Upload Process:**
1. Zip `input/` folder
2. Upload to Canvas Files
3. Select "Unpack this file"
4. **Never move or rename files**

**Limitations:**
- Cannot link to Canvas Assignments, Quizzes, or Pages
- 130KB file size limit for reliable relative paths

---

### 4.2 Workflow B: Placeholders + Post-Processing (Single Course)

**Use Case:** Development outside RCE with links to Canvas objects  
**Survives Course Copy:** ❌ No (requires post-copy script)

**Local Development:**
```html
<!-- syllabus.html -->
<a href="{{ASSIGNMENT_1_URL}}">Assignment 1</a>
<a href="{{SYLLABUS_URL}}">Syllabus</a>
```

**Config File:**
```json
// canvas-urls.json
{
  "ASSIGNMENT_1_URL": "/courses/123456/assignments/789012",
  "SYLLABUS_URL": "/courses/123456/files/987654/download"
}
```

**Post-Processing Script (Node.js example):**
```javascript
const fs = require('fs');
const config = require('./input/canvas-urls.json');

let content = fs.readFileSync('./input/syllabus.html', 'utf8');
for (const [key, value] of Object.entries(config)) {
  content = content.replace(new RegExp(`{{${key}}}`, 'g'), value);
}
fs.writeFileSync('./build/syllabus.html', content);
```

**Upload:** Zip `build/` and upload to Canvas Files

**Limitation:** URLs break when course is copied to new semester

---

### 4.3 Workflow C: Full Automation (Survives Course Copy)

**Use Case:** Production workflow requiring course copy resilience  
**Survives Course Copy:** ✅ Yes (with post-copy script)

**Requirements:**
- Canvas API token
- Node.js/Python environment
- Post-copy execution

**Three-Stage Process:**

**Stage 1: Local Development**
```html
<!-- Use placeholders -->
<a href="{{ASSIGNMENT_1_URL}}">Assignment 1</a>
```

**Stage 2: Initial Upload Script**
1. Fetch current course ID and content IDs via API
2. Inject URLs into placeholders
3. Upload processed files to Canvas

**Stage 3: Post-Copy Script** (Critical)
1. Trigger after course copy via API or manually
2. Fetch **new** course ID and all content IDs
3. Download all HTML files from new course
4. Update placeholders with **new** URLs
5. Re-upload files to new course

**Script Outline:**
```javascript
// post-copy-script.js
const axios = require('axios');
const CANVAS_API_TOKEN = process.env.CANVAS_TOKEN;
const NEW_COURSE_ID = process.argv[2];

async function updateLinks() {
  // 1. Get all assignments from new course
  const assignments = await getAssignments(NEW_COURSE_ID);
  
  // 2. Get all files from new course  
  const files = await getFiles(NEW_COURSE_ID);
  
  // 3. Download HTML files
  const htmlFiles = await downloadHtmlFiles(NEW_COURSE_ID);
  
  // 4. Update placeholders with new URLs
  const updatedFiles = htmlFiles.map(f => 
    replacePlaceholders(f, { assignments, files, courseId: NEW_COURSE_ID })
  );
  
  // 5. Re-upload
  await uploadFiles(NEW_COURSE_ID, updatedFiles);
}
```

---

### 4.4 Workflow D: External Hosting with Iframes

**Use Case:** Full control, no Canvas Files limitations  
**Survives Course Copy:** ✅ Yes (external URLs don't change)

**Hosting Options:**
- GitHub Pages
- Netlify
- AWS S3 + CloudFront
- Institutional web server

**Canvas Integration:**
```html
<!-- In Canvas Page or Assignment -->
<iframe 
  src="https://yourusername.github.io/course-repo/syllabus.html" 
  width="100%" 
  height="800px">
</iframe>
```

**Pros:**
- Full local development control
- No 130KB limit
- No broken links on course copy
- Can use modern web dev tools

**Cons:**
- External dependency
- Students leave Canvas UI
- Potential CORS issues
- Requires internet access

---

### 4.5 Workflow E: Hybrid (Recommended)

**Use Case:** Balance of local development and Canvas integration  
**Survives Course Copy:** ✅ Yes (for HTML-to-HTML links)

**Structure:**
```
input/
├── content/
│   ├── syllabus.html          # Links to other HTML via relative paths
│   ├── module-1.html
│   └── module-2.html
└── assets/
    └── css/
```

**Canvas Setup:**
1. Upload `input/` to Canvas Files (unpacked)
2. Create Canvas Assignments separately
3. Use **Modules** to organize:
   ```
   Module: Week 1
   ├── [File] syllabus.html
   ├── [File] module-1.html
   ├── [Assignment] Assignment 1
   └── [Assignment] Assignment 2
   ```

**Linking Strategy:**
- HTML files link to **other HTML files** (relative paths)
- **No** links from HTML to Canvas Assignments
- Students navigate via **Modules**, not via links in HTML

**Pros:**
- Local development with good tooling
- No broken internal HTML links
- Survives course copy
- Minimal RCE usage

**Cons:**
- Cannot deep-link from HTML to specific Canvas items
- Requires discipline to keep links internal only

---

## 5. Comparative Analysis

| Method | Local Dev | Link Survival | Canvas Features | Complexity | External Deps |
|--------|-----------|---------------|----------------|------------|----------------|
| Pure Local HTML | ✅ Excellent | ✅ Conditional | ❌ None | Low | ❌ None |
| Placeholders + Single Script | ✅ Excellent | ❌ No | ✅ All | Medium | ❌ None |
| Full Automation | ✅ Excellent | ✅ Yes | ✅ All | High | ❌ None |
| External Hosting | ✅ Excellent | ✅ Yes | ❌ Limited | Medium | ✅ Yes |
| Hybrid (Recommended) | ✅ Excellent | ✅ Yes | ✅ All | Medium | ❌ None |
| Native RCE | ❌ Poor | ✅ Yes | ✅ All | Low | ❌ None |

---

## 6. Critical Limitations & Caveats

### 6.1 The 130KB Threshold

**Problem:** Files exceeding ~130KB are automatically moved to S3 storage (`instructure-uploads.s3.amazonaws.com`), breaking all relative paths.

**Workarounds:**
- Keep HTML files under 130KB
- Split large pages into multiple smaller files
- Use external hosting for large content
- Avoid embedding large media directly in HTML

### 6.2 Course Copy Behavior

**What Works:**
- Canvas's official copy/import tools update **native internal references**
- Same-filename file replacements update links throughout course

**What Breaks:**
- All URLs in uploaded HTML files
- Manually copied/pasted content
- Links to deleted content

### 6.3 No Magic Bullet

**Hard Truth:** There is no way to write local HTML links that automatically become valid, course-copy-surviving Canvas links upon upload. This is a fundamental architectural limitation of Canvas.

**Why:** Canvas treats uploaded HTML files as static assets, not as integrated course content. Only content created through the RCE participates in Canvas's internal reference system.

---

## 7. Recommendations

### 7.1 For Most Users: Hybrid Workflow

**Use:** Workflow E (Hybrid)

**Rationale:**
- Maximizes local development time
- Avoids 130KB issues with proper file organization
- Survives course copying
- Minimal RCE interaction
- Uses Canvas's strength (Modules) for organization

### 7.2 For Advanced Users: Full Automation

**Use:** Workflow C (Full Automation)

**Rationale:**
- Only method that allows local development AND Canvas object links AND course copy survival
- Requires API integration
- Best for institutions with technical support

### 7.3 For Simple Content: Pure Local HTML

**Use:** Workflow A (Pure Local HTML)

**Rationale:**
- Simplest approach
- Works for self-contained content
- No Canvas integration needed

### 7.4 Avoid: Placeholders Without Post-Copy Script

**Do not use:** Workflow B alone

**Rationale:**
- URLs will break when course is copied
- Creates technical debt
- Requires manual fix each semester

---

## 8. Tooling Suggestions

### 8.1 Local Development
- **Editor:** VS Code with HTML/CSS/JS extensions
- **Preview:** `python -m http.server` or `live-server` npm package
- **Validation:** HTMLHint, Link Checker extensions

### 8.2 Build Processing
- **Language:** Node.js (easiest for most) or Python
- **Libraries:** 
  - Node: `axios` (API), `cheerio` (HTML parsing)
  - Python: `requests`, `BeautifulSoup`

### 8.3 Canvas API
- **Documentation:** [Canvas API Docs](https://canvas.instructure.com/doc/api/)
- **Authentication:** OAuth2 or API token
- **Key Endpoints:**
  - `GET /api/v1/courses/{course_id}/assignments`
  - `GET /api/v1/courses/{course_id}/files`
  - `GET /api/v1/courses/{course_id}/pages`

---

## 9. Conclusion

**Primary Finding:** Canvas LMS provides no native support for automatic link conversion in uploaded HTML files. This is a fundamental architectural limitation.

**Practical Implication:** Users seeking to develop course content outside the RCE must choose between:
1. **Self-contained HTML** with relative paths (limited functionality)
2. **Post-copy automation** to update URLs (technical complexity)
3. **External hosting** with iframes (external dependency)
4. **Hybrid approach** combining local HTML with Canvas Modules (recommended balance)

**Recommendation:** The Hybrid Workflow (Workflow E) offers the best balance of local development flexibility, link reliability, and Canvas integration for most users.

**Future Consideration:** Instructure could improve this situation by:
- Adding a `canvas://` URI scheme for local development
- Providing URL rewriting for uploaded HTML
- Extending internal reference system to Files section
- Documenting a migration-safe linking standard

---

## Appendix A: Key Sources

1. [Instructure Community: Relative links to media break when HTML files become too large](https://community.canvaslms.com/t5/Canvas-Instructional-Designer/Relative-links-to-media-break-when-HTML-files-become-too-large/m-p/139023)
2. [Emerson College: Understanding Links in Canvas](https://websites.emerson.edu/itg/understanding-links-in-canvas/)
3. [FSU: Canvas Best Practices](https://support.canvas.fsu.edu/kb/article/1108-canvas-best-practices/)
4. [UNM: Migration Cleanup](https://canvasinfo.unm.edu/move-to-canvas/migration-cleanup.html)
5. [Canvas API: Endpoint Attributes](https://canvas.instructure.com/doc/api/file.endpoint_attributes.html)
6. [Emerson College: Did You Know: Canvas Lets You Update Files!](https://websites.emerson.edu/itg/did-you-know-canvas-lets-you-update-files/)

---

## Appendix B: Quick Reference

### Relative Path Examples
```
Same directory:        href="page.html"
Subdirectory:          href="sub/page.html"
Parent directory:      href="../page.html"
Grandparent:           href="../../page.html"
```

### Canvas URL Patterns
```
Assignment:    /courses/{course_id}/assignments/{assignment_id}
File:          /courses/{course_id}/files/{file_id}/download
Page:          /courses/{course_id}/pages/{page_url}
Module:        /courses/{course_id}/modules/items/{module_item_id}
```

### File Size Limit
- **Threshold:** ~130KB
- **Behavior:** Files above limit moved to S3, breaking relative paths
- **Workaround:** Split content, use external hosting, or keep files small

---

*Document generated by Mistral Vibe CLI agent. Research conducted July 11, 2026.*

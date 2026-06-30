import unittest

import citation_pipeline


class CitationPipelineTests(unittest.TestCase):
    def test_extract_citations_supports_consecutive_references(self):
        citations = citation_pipeline.extract_citations("结论 A。[1][2]")

        self.assertEqual(citations, [1, 2])

    def test_remove_invalid_citations_keeps_valid_references(self):
        cleaned = citation_pipeline.remove_invalid_citations(
            "结论 A。[1][99][3]",
            valid_source_ids={1, 3},
        )

        self.assertEqual(cleaned, "结论 A。[1][3]")

    def test_convert_citations_to_links(self):
        converted = citation_pipeline.convert_citations_to_links(
            "结论 A。[1]",
            sources=[{"source_id": 1, "url": "https://a.com"}],
        )

        self.assertIn("[[1]](https://a.com)", converted)

    def test_convert_consecutive_citations_to_links(self):
        converted = citation_pipeline.convert_citations_to_links(
            "结论 A。[1][2]",
            sources=[
                {"source_id": 1, "url": "https://a.com"},
                {"source_id": 2, "url": "https://b.com"},
            ],
        )

        self.assertIn("[[1]](https://a.com)[[2]](https://b.com)", converted)

    def test_source_without_url_keeps_plain_citation(self):
        converted = citation_pipeline.convert_citations_to_links(
            "结论 A。[1]",
            sources=[{"source_id": 1, "url": ""}],
        )

        self.assertEqual(converted, "结论 A。[1]")

    def test_reference_section_is_not_converted(self):
        converted = citation_pipeline.process_report_citations(
            "结论 A。[1]\n\n## 7. 参考来源\n[1] title - https://a.com",
            sources=[{"source_id": 1, "url": "https://a.com"}],
        )

        self.assertIn("结论 A。[[1]](https://a.com)", converted)
        self.assertIn("## 7. 参考来源\n[1] title - https://a.com", converted)


if __name__ == "__main__":
    unittest.main()

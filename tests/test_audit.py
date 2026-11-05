import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from paraphrasing_claim_audit.audit import audit, has_evidence, main, match_phrases, prose
from paraphrasing_claim_audit.phrases import PARAPHRASE, NOPARAPHRASE, GENERIC_NAMES


class AuditTests(unittest.TestCase):
    def test_phrase_oracle(self):
        self.assertEqual(PARAPHRASE, EXPECTED_POSITIVE)
        self.assertEqual(NOPARAPHRASE, EXPECTED_NEGATIVE)

    def test_generic_oracle(self):
        self.assertEqual(GENERIC_NAMES, EXPECTED_GENERIC)

    def fixture(self, text='', source='', test=False):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        target = root / ('tests/fixture.md' if test else 'README.md')
        target.parent.mkdir(exist_ok=True)
        target.write_text(text)
        (root / 'app.py').write_text(source)
        return root

    def cli(self, root, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(['audit', str(root)] + list(args))
        return code, out.getvalue()

    def test_span_removal(self):
        self.assertEqual(audit(self.fixture('does not paraphrase')), [])

    def test_longest_first(self):
        self.assertEqual(match_phrases('paraphrase generation', PARAPHRASE)[0], ['paraphrase generation'])

    def test_case(self):
        self.assertEqual(audit(self.fixture('PARAPHRASING'))[0]['severity'], 'HIGH')

    def test_fenced(self):
        self.assertEqual(audit(self.fixture('```text\nparaphrasing\n```')), [])

    def test_inline(self):
        self.assertEqual(len(audit(self.fixture('`paraphrasing`'))), 1)

    def test_cli_good(self):
        self.assertEqual(self.cli(self.fixture('paraphrase', 'x.paraphrase()')), (0, 'PASS\n'))

    def test_cli_bad(self):
        code, out = self.cli(self.fixture('paraphrase'))
        self.assertEqual(code, 2)
        self.assertIn('HIGH documented-paraphrasing-claim-false', out)

    def test_cli_test_only(self):
        root = self.fixture('paraphrase', test=True)
        code, out = self.cli(root)
        self.assertEqual(code, 0)
        self.assertIn('MEDIUM documented-paraphrasing-claim-false', out)
        self.assertEqual(self.cli(root, '--fail-on', 'medium')[0], 2)

    def test_cli_denial(self):
        code, out = self.cli(self.fixture('does not paraphrase', 'x.paraphrase()'))
        self.assertEqual(code, 2)
        self.assertIn('HIGH documented-no-paraphrasing-claim-false', out)

    def test_cli_no_claim(self):
        self.assertEqual(self.cli(self.fixture('Hello')), (0, 'PASS\n'))

    def test_cli_json(self):
        code, out = self.cli(self.fixture('paraphrase'), '--json')
        self.assertEqual(code, 2)
        finding = json.loads(out)[0]
        self.assertEqual(finding['verdict'], 'documented-paraphrasing-claim-false')
        self.assertTrue(finding['message'])

    def test_version(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as exc:
            main(['--version'])
        self.assertEqual(exc.exception.code, 0)
        self.assertEqual(out.getvalue(), '0.1.0\n')

    def test_ignore(self):
        self.assertEqual(self.cli(self.fixture('paraphrase'), '--ignore', 'README')[0], 0)

    def test_readme(self):
        root = Path(__file__).resolve().parents[1]
        text = prose((root / 'README.md').read_text())
        self.assertEqual(match_phrases(text, PARAPHRASE + NOPARAPHRASE)[0], [])
        self.assertEqual(self.cli(root)[0], 0)

    def test_split_modules(self):
        root = self.fixture('paraphrase', 'from transformers import AutoModelForSeq2SeqLM\nm=AutoModelForSeq2SeqLM.from_pretrained("paraphrase")')
        (root / 'other.py').write_text('m.generate()')
        self.assertEqual(audit(root)[0]['severity'], 'HIGH')

    def test_docs_scope(self):
        root = self.fixture()
        (root/'docs/deep').mkdir(parents=True)
        (root/'docs/deep/a.md').write_text('paraphrase')
        self.assertEqual(len(audit(root)), 1)

    def test_usage_and_io(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
            main(['audit', '--unknown'])
        self.assertEqual(exc.exception.code, 1)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['audit', '/nonexistent/r141']), 1)

    def test_excluded_evidence(self):
        root = self.fixture('paraphrase')
        for directory in ('.git', '__pycache__', '.venv', 'venv'):
            (root/directory).mkdir()
            (root/directory/'x.py').write_text('x.paraphrase()')
        self.assertEqual(len(audit(root)), 1)

EXPECTED_POSITIVE = ['paraphrase generation', 'paraphrase', 'paraphrases', 'paraphrasing', 'paraphrased', 'paraphrase model', 'paraphrase models', 'paraphraser', 'generates paraphrases', 'generate paraphrases', 'paraphrase support', 'supports paraphrasing', 'provides paraphrasing', 'performs paraphrasing', 'paraphrasing feature', 'paraphrasing capability', 'paraphrasing system', 'paraphrasing pipeline', 'paraphrasing step', 'paraphrasing process', 'paraphrase feature', 'paraphrase capability', 'automatic paraphrasing', 'auto paraphrasing', 'paraphrase text', 'paraphrases text', 'paraphrase sentences', 'paraphrases sentences', 'paraphrase a sentence', 'paraphrase sentence', 'rephrase', 'rephrases', 'rephrasing', 'rephrased', 'rephrase text', 'rephrases text', 'rephrase a sentence', 'rephrase sentences', 'rephrases sentences', 'sentence paraphrasing', 'text paraphrasing', 'paraphrase quality', 'paraphrase tool', 'paraphrasing tool', 'paraphrase engine', 'paraphrasing engine', 'paraphrase api', 'paraphrasing api', 'paraphrase generation support', 'supports paraphrase generation']
EXPECTED_NEGATIVE = ['does not paraphrase', 'do not paraphrase', "doesn't paraphrase", "don't paraphrase", 'no paraphrasing', 'without paraphrasing', 'never paraphrases', 'does not perform paraphrasing', 'never performs paraphrasing', 'paraphrasing not supported', 'paraphrasing unsupported', 'no paraphrase support', 'lacks paraphrasing', 'missing paraphrasing', 'paraphrasing disabled', 'no paraphrase', 'without paraphrasing support', 'does not provide paraphrasing', 'does not support paraphrasing', 'no automatic paraphrasing', 'paraphrasing not available', 'no paraphrase generation', 'does not generate paraphrases', 'without a paraphraser']
EXPECTED_GENERIC = ['paraphrase', 'paraphrase_text', 'paraphrase_sentence', 'paraphrase_paragraph', 'paraphrase_document', 'generate_paraphrase', 'generate_paraphrases', 'get_paraphrase', 'get_paraphrases', 'create_paraphrase', 'create_paraphrases', 'produce_paraphrase', 'produce_paraphrases', 'rephrase', 'rephrase_text', 'rephrase_sentence', 'rephrase_paragraph', 'get_rephrase', 'generate_rephrase', 'paraphrasing', 'paraphrase_input', 'paraphrase_output', 'paraphrase_batch', 'batch_paraphrase']

POSITIVE_CASES = {'AutoModelForSeq2SeqLM_assigned': 'from transformers import AutoModelForSeq2SeqLM as M\nm=M.from_pretrained("org/PARAPHRASE-model")\nm.generate()', 'AutoModelForSeq2SeqLM_chained': 'import transformers as tf\ntf.AutoModelForSeq2SeqLM.from_pretrained("paraphrase").generate()', 'PegasusForConditionalGeneration_assigned': 'from transformers import PegasusForConditionalGeneration as M\nm=M.from_pretrained("org/PARAPHRASE-model")\nm.generate()', 'PegasusForConditionalGeneration_chained': 'import transformers as tf\ntf.PegasusForConditionalGeneration.from_pretrained("paraphrase").generate()', 'T5ForConditionalGeneration_assigned': 'from transformers import T5ForConditionalGeneration as M\nm=M.from_pretrained("org/PARAPHRASE-model")\nm.generate()', 'T5ForConditionalGeneration_chained': 'import transformers as tf\ntf.T5ForConditionalGeneration.from_pretrained("paraphrase").generate()', 'pipeline_6': 'from transformers import pipeline as p\nv=p("text2text-generation", model="paraphrase")\nv("text")', 'pipeline_7': 'from transformers import pipeline as p\np("text2text-generation", model="paraphrase")("text")', 'pipeline_8': 'from transformers import pipeline as p\nv=p("text2text-generation", "paraphrase")\nv("text")', 'pipeline_9': 'from transformers import pipeline as p\np("text2text-generation", "paraphrase")("text")', 'mining_attr': 'import sentence_transformers as st\nst.util.paraphrase_mining(model, texts)', 'mining_bare': 'from sentence_transformers.util import paraphrase_mining as mine\nmine(model,texts)', 'back_assigned': 'import nlpaug.augmenter.word as naw\na=naw.BackTranslationAug()\na.augment("text")', 'back_chained': 'from nlpaug.augmenter.word import BackTranslationAug as B\nB().augment("text")', 'generic_attr_paraphrase': 'x.paraphrase()', 'generic_alias_paraphrase': 'from custom import paraphrase as f\nf()', 'generic_attr_paraphrase_text': 'x.paraphrase_text()', 'generic_alias_paraphrase_text': 'from custom import paraphrase_text as f\nf()', 'generic_attr_paraphrase_sentence': 'x.paraphrase_sentence()', 'generic_alias_paraphrase_sentence': 'from custom import paraphrase_sentence as f\nf()', 'generic_attr_paraphrase_paragraph': 'x.paraphrase_paragraph()', 'generic_alias_paraphrase_paragraph': 'from custom import paraphrase_paragraph as f\nf()', 'generic_attr_paraphrase_document': 'x.paraphrase_document()', 'generic_alias_paraphrase_document': 'from custom import paraphrase_document as f\nf()', 'generic_attr_generate_paraphrase': 'x.generate_paraphrase()', 'generic_alias_generate_paraphrase': 'from custom import generate_paraphrase as f\nf()', 'generic_attr_generate_paraphrases': 'x.generate_paraphrases()', 'generic_alias_generate_paraphrases': 'from custom import generate_paraphrases as f\nf()', 'generic_attr_get_paraphrase': 'x.get_paraphrase()', 'generic_alias_get_paraphrase': 'from custom import get_paraphrase as f\nf()', 'generic_attr_get_paraphrases': 'x.get_paraphrases()', 'generic_alias_get_paraphrases': 'from custom import get_paraphrases as f\nf()', 'generic_attr_create_paraphrase': 'x.create_paraphrase()', 'generic_alias_create_paraphrase': 'from custom import create_paraphrase as f\nf()', 'generic_attr_create_paraphrases': 'x.create_paraphrases()', 'generic_alias_create_paraphrases': 'from custom import create_paraphrases as f\nf()', 'generic_attr_produce_paraphrase': 'x.produce_paraphrase()', 'generic_alias_produce_paraphrase': 'from custom import produce_paraphrase as f\nf()', 'generic_attr_produce_paraphrases': 'x.produce_paraphrases()', 'generic_alias_produce_paraphrases': 'from custom import produce_paraphrases as f\nf()', 'generic_attr_rephrase': 'x.rephrase()', 'generic_alias_rephrase': 'from custom import rephrase as f\nf()', 'generic_attr_rephrase_text': 'x.rephrase_text()', 'generic_alias_rephrase_text': 'from custom import rephrase_text as f\nf()', 'generic_attr_rephrase_sentence': 'x.rephrase_sentence()', 'generic_alias_rephrase_sentence': 'from custom import rephrase_sentence as f\nf()', 'generic_attr_rephrase_paragraph': 'x.rephrase_paragraph()', 'generic_alias_rephrase_paragraph': 'from custom import rephrase_paragraph as f\nf()', 'generic_attr_get_rephrase': 'x.get_rephrase()', 'generic_alias_get_rephrase': 'from custom import get_rephrase as f\nf()', 'generic_attr_generate_rephrase': 'x.generate_rephrase()', 'generic_alias_generate_rephrase': 'from custom import generate_rephrase as f\nf()', 'generic_attr_paraphrasing': 'x.paraphrasing()', 'generic_alias_paraphrasing': 'from custom import paraphrasing as f\nf()', 'generic_attr_paraphrase_input': 'x.paraphrase_input()', 'generic_alias_paraphrase_input': 'from custom import paraphrase_input as f\nf()', 'generic_attr_paraphrase_output': 'x.paraphrase_output()', 'generic_alias_paraphrase_output': 'from custom import paraphrase_output as f\nf()', 'generic_attr_paraphrase_batch': 'x.paraphrase_batch()', 'generic_alias_paraphrase_batch': 'from custom import paraphrase_batch as f\nf()', 'generic_attr_batch_paraphrase': 'x.batch_paraphrase()', 'generic_alias_batch_paraphrase': 'from custom import batch_paraphrase as f\nf()'}
NEGATIVE_CASES = {'imports': 'from transformers import AutoModelForSeq2SeqLM, pipeline\nfrom sentence_transformers.util import paraphrase_mining\nfrom nlpaug.augmenter.word import BackTranslationAug\nfrom x import paraphrase', 'summarization': 'from transformers import pipeline\npipeline("summarization")("text")', 'gensim': 'import gensim\ngensim.summarization.summarize("text")', 'sumy': 'from sumy.summarizers.lsa import LsaSummarizer\ns=LsaSummarizer()\ns.summarize("text")', 'marian': 'from transformers import MarianMTModel\nm=MarianMTModel.from_pretrained("translation")\nm.generate()', 'raw_back': 'translator.translate(translator.translate("text", "fr"), "en")', 'pipeline_lone': 'from transformers import pipeline\np=pipeline("text2text-generation", model="paraphrase")', 'back_lone': 'from nlpaug.augmenter.word import BackTranslationAug\na=BackTranslationAug()', 'strings': '"""paraphrase rephrase"""\ns="paraphrase"\n# x.paraphrase()', 'unbound': 'from x import paraphrase\nparaphrase', 'shadow_generic': 'from x import paraphrase\ndef paraphrase(): pass\nparaphrase()', 'shadow_class': 'from transformers import AutoModelForSeq2SeqLM\nclass AutoModelForSeq2SeqLM: pass\nm=AutoModelForSeq2SeqLM.from_pretrained("paraphrase")\nm.generate()', 'shadow_attr': 'import transformers as tf\nclass AutoModelForSeq2SeqLM: pass\ntf.AutoModelForSeq2SeqLM.from_pretrained("paraphrase").generate()', 'subprocess': 'import subprocess\nsubprocess.run(["paraphrase", "text"])', 'wrong_instance': 'from transformers import AutoModelForSeq2SeqLM as M\nm=M.from_pretrained("paraphrase")\nother.generate()', 'wrong_pipeline': 'from transformers import pipeline\np=pipeline("translation", model="paraphrase")\np("text")', 'lone_AutoModelForSeq2SeqLM': 'from transformers import AutoModelForSeq2SeqLM\nm=AutoModelForSeq2SeqLM.from_pretrained("paraphrase")', 'nonmatching_AutoModelForSeq2SeqLM': 'from transformers import AutoModelForSeq2SeqLM\nm=AutoModelForSeq2SeqLM.from_pretrained("summarizer")\nm.generate()', 'lone_PegasusForConditionalGeneration': 'from transformers import PegasusForConditionalGeneration\nm=PegasusForConditionalGeneration.from_pretrained("paraphrase")', 'nonmatching_PegasusForConditionalGeneration': 'from transformers import PegasusForConditionalGeneration\nm=PegasusForConditionalGeneration.from_pretrained("summarizer")\nm.generate()', 'lone_T5ForConditionalGeneration': 'from transformers import T5ForConditionalGeneration\nm=T5ForConditionalGeneration.from_pretrained("paraphrase")', 'nonmatching_T5ForConditionalGeneration': 'from transformers import T5ForConditionalGeneration\nm=T5ForConditionalGeneration.from_pretrained("summarizer")\nm.generate()', 'other_sentiment_analysis': 'from transformers import pipeline\npipeline("sentiment-analysis")("text")', 'other_ner': 'from transformers import pipeline\npipeline("ner")("text")', 'other_part_of_speech': 'from transformers import pipeline\npipeline("part-of-speech")("text")', 'other_tokenization': 'from transformers import pipeline\npipeline("tokenization")("text")', 'other_stemming': 'from transformers import pipeline\npipeline("stemming")("text")', 'other_lemmatization': 'from transformers import pipeline\npipeline("lemmatization")("text")', 'other_keyword_extraction': 'from transformers import pipeline\npipeline("keyword-extraction")("text")', 'other_topic_modeling': 'from transformers import pipeline\npipeline("topic-modeling")("text")', 'other_translation': 'from transformers import pipeline\npipeline("translation")("text")'}

def positive(source):
    def test(self):
        self.assertTrue(has_evidence(source), source)
    return test


def negative(source):
    def test(self):
        self.assertFalse(has_evidence(source), source)
    return test


for name, source in POSITIVE_CASES.items():
    setattr(AuditTests, 'test_evidence_' + name, positive(source))
for name, source in NEGATIVE_CASES.items():
    setattr(AuditTests, 'test_reject_' + name, negative(source))

from main import build_parser


def test_new_cleanup_flags_defaults():
    args = build_parser().parse_args(["video.mov"])
    assert args.cleanup == "full"
    assert args.cue_word == "rifaccio"
    assert args.retranscribe is False
    assert args.no_metadata is False


def test_cleanup_flags_parse():
    args = build_parser().parse_args(["video.mov", "--cleanup", "rules", "--cue-word", "",
                                      "--retranscribe", "--no-metadata"])
    assert (args.cleanup, args.cue_word, args.retranscribe, args.no_metadata) == ("rules", "", True, True)

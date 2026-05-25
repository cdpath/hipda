from hipda_cli.parser import is_login_required_page, parse_forum_listing, parse_thread


LISTING_HTML = """
<html><body>
<table>
  <tr class="thread">
    <th><a href="viewthread.php?tid=3446553&extra=page%3D1">《放开那个女巫》动画做得还不错。</a></th>
    <td class="author">老兵-猫族<br>2026-5-7</td>
    <td class="nums">11/777</td>
    <td class="lastpost">leeice<br>2026-5-8 11:56</td>
  </tr>
  <tr>
    <th><a href="viewthread.php?tid=3447001">iPhone13PM手机更换电池，现在最好的姿势是啥？</a></th>
    <td>死老妖<br>2026-5-8</td>
    <td>0/4</td>
    <td>死老妖<br>2026-5-8 11:55</td>
  </tr>
</table>
</body></html>
"""

REALISTIC_LISTING_HTML = """
<html><body>
<tbody id="normalthread_3057651">
<tr>
  <td class="folder"><a href="viewthread.php?tid=3057651&amp;extra=page%3D1"><img src="folder.gif"></a></td>
  <td class="icon">&nbsp;</td>
  <th class="subject lock">
    <span id="thread_3057651"><a href="viewthread.php?tid=3057651&amp;extra=page%3D1">hipda已迁移到新域名4d4y</a></span>
  </th>
  <td class="author"><cite><a href="space.php?uid=29">4d4y</a></cite><em>2022-6-13</em></td>
  <td class="nums"><strong>0</strong>/<em>90106</em></td>
  <td class="lastpost"><cite><a href="space.php?username=4d4y">4d4y</a></cite><em><a>2022-6-13 22:57</a></em></td>
</tr>
</tbody>
<tbody>
<tr><td class="folder"></td><td>&nbsp;</td><th class="subject">版块主题</th><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
</tbody>
<tbody id="normalthread_3449572">
<tr>
  <td class="folder"><a href="viewthread.php?tid=3449572&amp;extra=page%3D1"><img src="folder_new.gif"></a></td>
  <td class="icon">&nbsp;</td>
  <th class="subject new">
    <span id="thread_3449572"><a href="viewthread.php?tid=3449572&amp;extra=page%3D1">半导体依然疯了.....</a></span>
  </th>
  <td class="author"><cite><a href="space.php?uid=521637">yasool</a></cite><em>2026-5-25</em></td>
  <td class="nums"><strong>15</strong>/<em>517</em></td>
  <td class="lastpost"><cite><a href="space.php?username=yasool">yasool</a></cite><em><a>2026-5-25 13:58</a></em></td>
</tr>
</tbody>
</body></html>
"""


THREAD_HTML = """
<html><body>
<div id="post_1">
  <div class="postauthor">老兵-猫族</div>
  <div class="postinfo">发表于 2026-5-7 19:12</div>
  <td class="t_msgfont">动画做得还不错。<br>节奏可以。</td>
</div>
<div id="post_2">
  <div class="postauthor">leeice</div>
  <div class="postinfo">发表于 2026-5-8 11:56</div>
  <td class="t_msgfont">谢谢推荐</td>
</div>
</body></html>
"""

REALISTIC_THREAD_HTML = """
<html><body>
<div id="post_74215032">
  <table><tr>
    <td class="postauthor">
      <div class="postinfo"><a href="space.php?uid=277860">死老妖</a></div>
      <dl class="profile"><dt>UID</dt><dd>277860</dd></dl>
    </td>
    <td class="postcontent">
      <div class="postinfo">
        <div class="authorinfo"><em id="authorposton74215032">发表于 2026-5-8 11:55</em></div>
      </div>
      <div class="postmessage firstpost">
        <td class="t_msgfont" id="postmessage_74215032">不要弹窗、要大容量</td>
      </div>
    </td>
  </tr></table>
</div>
</body></html>
"""


def test_parse_forum_listing_extracts_threads_and_stats():
    threads = parse_forum_listing(LISTING_HTML, base_url="https://www.4d4y.com/forum/")

    assert [thread.tid for thread in threads] == ["3446553", "3447001"]
    assert threads[0].title == "《放开那个女巫》动画做得还不错。"
    assert threads[0].author == "老兵-猫族"
    assert threads[0].replies == 11
    assert threads[0].views == 777
    assert threads[0].last_author == "leeice"
    assert threads[0].url == "https://www.4d4y.com/forum/viewthread.php?tid=3446553&extra=page%3D1"


def test_parse_forum_listing_uses_subject_link_when_icon_link_shares_tid():
    threads = parse_forum_listing(REALISTIC_LISTING_HTML, base_url="https://www.4d4y.com/forum/")

    assert len(threads) == 2
    assert threads[0].tid == "3057651"
    assert threads[0].title == "hipda已迁移到新域名4d4y"
    assert threads[0].author == "4d4y"
    assert threads[0].created_at == "2022-6-13"
    assert threads[0].replies == 0
    assert threads[0].views == 90106
    assert threads[0].last_author == "4d4y"
    assert threads[0].last_at == "2022-6-13 22:57"
    assert threads[0].is_pinned is True
    assert threads[1].tid == "3449572"
    assert threads[1].is_pinned is False


def test_parse_thread_extracts_posts():
    posts = parse_thread(THREAD_HTML)

    assert [post.author for post in posts] == ["老兵-猫族", "leeice"]
    assert posts[0].published_at == "2026-5-7 19:12"
    assert posts[0].content == "动画做得还不错。\n节奏可以。"


def test_parse_thread_uses_discuz_author_and_date_without_sidebar_noise():
    posts = parse_thread(REALISTIC_THREAD_HTML)

    assert len(posts) == 1
    assert posts[0].author == "死老妖"
    assert posts[0].published_at == "2026-5-8 11:55"
    assert posts[0].content == "不要弹窗、要大容量"


def test_parse_thread_extracts_pid_from_post_container_id():
    posts = parse_thread(THREAD_HTML)
    realistic_posts = parse_thread(REALISTIC_THREAD_HTML)

    assert [post.pid for post in posts] == ["1", "2"]
    assert [post.pid for post in realistic_posts] == ["74215032"]


def test_detects_login_required_page():
    html = "<html><title>提示信息</title><body>对不起，您还未登录，无权访问该版块。</body></html>"

    assert is_login_required_page(html) is True

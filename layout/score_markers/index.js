LoadEverything().then(() => {
  Start = async () => {};

  Update = async (event) => {
    let data = event.data;
    let oldData = event.oldData;

    // window.team

    let src = "";

    if (_.get(data, "score.best_of")) {
      let html = "";
      for (let i = 0; i < _.get(data, "score.best_of"); i += 1) {
        if (_.get(data, "score.team.1.score", 0) > i) {
          html += "<img src='./t1_game_win.svg' />";
        } else {
          html += "<img src='./t1_game_base.svg' />";
        }
      }
      $(".container").html(html);
    } else {
      let html = "";
      for (let i = 0; i < _.get(data, "score.team.1.score", 0); i += 1) {
        html += "<img src='./t1_game_win.svg' />";
      }
      $(".container").html(html);
    }
  };
});
